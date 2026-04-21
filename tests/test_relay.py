"""
M4 跨域中继测试 - alpha <-> beta 跨域邮件收发与撤回
"""
import asyncio
import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.protocol import Action, StatusCode, build_request
from shared.crypto import compute_hmac
from server.main import EmailServer
from server.config import ServerConfig
from client.connection import Connection


@pytest.fixture
def alpha_config():
    """Alpha 服务器配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18030
    config.data_dir = "./data/test_relay_alpha"
    config.security.jwt_secret = "alpha-relay-test-secret"
    config.security.bcrypt_cost = 4
    config.security.recall_window_minutes = 5
    from server.config import PeerConfig, S2SConfig
    config.s2s.peers = [PeerConfig(domain="beta.local", host="127.0.0.1", port=18031)]
    config.s2s.shared_secret = "test-s2s-shared-secret"
    return config


@pytest.fixture
def beta_config():
    """Beta 服务器配置"""
    config = ServerConfig()
    config.domain = "beta.local"
    config.host = "127.0.0.1"
    config.port = 18031
    config.data_dir = "./data/test_relay_beta"
    config.security.jwt_secret = "beta-relay-test-secret"
    config.security.bcrypt_cost = 4
    config.security.recall_window_minutes = 5
    from server.config import PeerConfig, S2SConfig
    config.s2s.peers = [PeerConfig(domain="alpha.local", host="127.0.0.1", port=18030)]
    config.s2s.shared_secret = "test-s2s-shared-secret"
    return config


@pytest.fixture
async def dual_servers(alpha_config, beta_config):
    """启动 alpha 和 beta 双服务器"""
    # 清理
    for cfg in [alpha_config, beta_config]:
        db_path = os.path.join(cfg.data_dir, "safeemail.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        os.makedirs(cfg.data_dir, exist_ok=True)

    alpha_server = EmailServer(alpha_config)
    beta_server = EmailServer(beta_config)

    await alpha_server._init_services()
    await beta_server._init_services()

    alpha_srv = await asyncio.start_server(
        alpha_server.handler.handle_connection,
        alpha_config.host, alpha_config.port
    )
    beta_srv = await asyncio.start_server(
        beta_server.handler.handle_connection,
        beta_config.host, beta_config.port
    )

    yield alpha_server, beta_server

    alpha_srv.close()
    beta_srv.close()
    await alpha_srv.wait_closed()
    await beta_srv.wait_closed()
    await alpha_server.db.close()
    await beta_server.db.close()


async def register_and_login(host, port, username, password="TestPass123"):
    """注册并登录用户"""
    conn = Connection(host, port)
    await conn.connect()
    await conn.request(Action.REGISTER, {"username": username, "password": password})
    resp = await conn.request(Action.LOGIN, {"username": username, "password": password})
    token = resp["payload"]["access_token"]
    return conn, token


class TestCrossDomainDelivery:
    """跨域邮件投递测试 (TC-001)"""

    @pytest.mark.asyncio
    async def test_alpha_to_beta_delivery(self, dual_servers, alpha_config, beta_config):
        """alpha 用户发邮件给 beta 用户，beta 收件箱能收到"""
        # alpha 侧注册发件人
        alpha_conn, alpha_token = await register_and_login(
            alpha_config.host, alpha_config.port, "alice"
        )
        # beta 侧注册收件人
        beta_conn, beta_token = await register_and_login(
            beta_config.host, beta_config.port, "bob"
        )

        try:
            # alice@alpha 发邮件给 bob@beta
            send_resp = await alpha_conn.request(Action.SEND_MAIL, {
                "to": ["bob@beta.local"],
                "subject": "跨域测试邮件",
                "body": "这是一封从 alpha 发往 beta 的邮件"
            }, token=alpha_token)

            assert send_resp["status"] == StatusCode.OK
            assert "bob@beta.local" in send_resp["payload"]["remote_recipients"]

            # 等待异步中继完成
            await asyncio.sleep(0.5)

            # bob@beta 检查收件箱
            inbox_resp = await beta_conn.request(Action.LIST_INBOX, {}, token=beta_token)
            assert inbox_resp["status"] == StatusCode.OK
            assert inbox_resp["payload"]["total"] >= 1

            # 验证邮件内容
            emails = inbox_resp["payload"]["emails"]
            cross_mail = next((e for e in emails if e["subject"] == "跨域测试邮件"), None)
            assert cross_mail is not None
            assert cross_mail["from_user"] == "alice@alpha.local"

        finally:
            await alpha_conn.close()
            await beta_conn.close()

    @pytest.mark.asyncio
    async def test_beta_to_alpha_delivery(self, dual_servers, alpha_config, beta_config):
        """beta 用户发邮件给 alpha 用户"""
        alpha_conn, alpha_token = await register_and_login(
            alpha_config.host, alpha_config.port, "charlie"
        )
        beta_conn, beta_token = await register_and_login(
            beta_config.host, beta_config.port, "dave"
        )

        try:
            # dave@beta -> charlie@alpha
            send_resp = await beta_conn.request(Action.SEND_MAIL, {
                "to": ["charlie@alpha.local"],
                "subject": "反向跨域",
                "body": "beta到alpha"
            }, token=beta_token)
            assert send_resp["status"] == StatusCode.OK

            await asyncio.sleep(0.5)

            # charlie@alpha 检查收件箱
            inbox_resp = await alpha_conn.request(Action.LIST_INBOX, {}, token=alpha_token)
            assert inbox_resp["status"] == StatusCode.OK
            emails = inbox_resp["payload"]["emails"]
            cross_mail = next((e for e in emails if e["subject"] == "反向跨域"), None)
            assert cross_mail is not None

        finally:
            await alpha_conn.close()
            await beta_conn.close()


class TestCrossDomainRecall:
    """跨域撤回测试"""

    @pytest.mark.asyncio
    async def test_cross_domain_recall(self, dual_servers, alpha_config, beta_config):
        """跨域邮件撤回"""
        alpha_conn, alpha_token = await register_and_login(
            alpha_config.host, alpha_config.port, "recall_alice"
        )
        beta_conn, beta_token = await register_and_login(
            beta_config.host, beta_config.port, "recall_bob"
        )

        try:
            # 发送跨域邮件
            send_resp = await alpha_conn.request(Action.SEND_MAIL, {
                "to": ["recall_bob@beta.local"],
                "subject": "跨域撤回测试",
                "body": "将被撤回"
            }, token=alpha_token)
            email_id = send_resp["payload"]["email_id"]

            await asyncio.sleep(0.5)

            # 撤回（本域撤回 + 触发S2S撤回）
            signature = compute_hmac(
                alpha_config.security.jwt_secret,
                f"RECALL:{email_id}:recall_alice@alpha.local"
            )
            recall_resp = await alpha_conn.request(Action.RECALL_MAIL, {
                "email_id": email_id,
                "signature": signature
            }, token=alpha_token)
            assert recall_resp["status"] == StatusCode.OK

        finally:
            await alpha_conn.close()
            await beta_conn.close()


class TestStorageIsolation:
    """存储隔离验证 (S-003)"""

    @pytest.mark.asyncio
    async def test_data_directories_isolated(self, dual_servers, alpha_config, beta_config):
        """验证两个域的数据目录完全隔离"""
        # 确认数据目录不同
        assert alpha_config.data_dir != beta_config.data_dir
        
        # 确认各自的数据库文件独立存在
        alpha_db = os.path.join(alpha_config.data_dir, "safeemail.db")
        beta_db = os.path.join(beta_config.data_dir, "safeemail.db")
        assert os.path.exists(alpha_db)
        assert os.path.exists(beta_db)
        assert alpha_db != beta_db

    @pytest.mark.asyncio
    async def test_user_isolation(self, dual_servers, alpha_config, beta_config):
        """验证用户数据隔离：alpha 用户看不到 beta 用户数据"""
        alpha_conn, alpha_token = await register_and_login(
            alpha_config.host, alpha_config.port, "iso_user_a"
        )
        beta_conn, beta_token = await register_and_login(
            beta_config.host, beta_config.port, "iso_user_b"
        )

        try:
            # beta 用户在 beta 域发邮件给本域用户
            await register_and_login(beta_config.host, beta_config.port, "iso_recv_b")
            await beta_conn.request(Action.SEND_MAIL, {
                "to": ["iso_recv_b@beta.local"],
                "subject": "Beta内部邮件",
                "body": "仅beta可见"
            }, token=beta_token)

            # alpha 用户查看自己收件箱，不应看到 beta 内部邮件
            inbox_resp = await alpha_conn.request(Action.LIST_INBOX, {}, token=alpha_token)
            emails = inbox_resp["payload"]["emails"]
            beta_mails = [e for e in emails if "Beta内部" in e.get("subject", "")]
            assert len(beta_mails) == 0

        finally:
            await alpha_conn.close()
            await beta_conn.close()

    @pytest.mark.asyncio
    async def test_path_traversal_protection(self, alpha_config, beta_config):
        """路径校验：禁止越权访问对方数据目录"""
        # 验证路径不会交叉
        alpha_path = os.path.abspath(alpha_config.data_dir)
        beta_path = os.path.abspath(beta_config.data_dir)
        
        # alpha 路径不是 beta 的子路径，反之亦然
        assert not alpha_path.startswith(beta_path)
        assert not beta_path.startswith(alpha_path)
