"""
M3 核心邮件功能测试 - 发送/收件箱/发件箱/草稿/群发/撤回
"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.protocol import Action, StatusCode, build_request
from shared.crypto import compute_hmac
from server.main import EmailServer
from server.config import ServerConfig
from client.connection import Connection


@pytest.fixture
def mail_config():
    """邮件测试服务器配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18020
    config.data_dir = "./data/test_mail"
    config.security.jwt_secret = "test-jwt-secret-mail"
    config.security.bcrypt_cost = 4
    config.security.recall_window_minutes = 5
    return config


@pytest.fixture
async def mail_server(mail_config):
    """启动邮件测试服务器"""
    db_path = os.path.join(mail_config.data_dir, "safeemail.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    server = EmailServer(mail_config)
    os.makedirs(mail_config.data_dir, exist_ok=True)
    await server._init_services()

    srv = await asyncio.start_server(
        server.handler.handle_connection,
        mail_config.host,
        mail_config.port
    )
    yield srv, server
    srv.close()
    await srv.wait_closed()
    await server.db.close()


@pytest.fixture
async def client(mail_config, mail_server):
    """客户端连接"""
    conn = Connection(mail_config.host, mail_config.port)
    await conn.connect()
    yield conn
    await conn.close()


async def register_and_login(client, username, password="TestPass123"):
    """辅助：注册并登录，返回 access_token"""
    await client.request(Action.REGISTER, {
        "username": username,
        "password": password
    })
    resp = await client.request(Action.LOGIN, {
        "username": username,
        "password": password
    })
    return resp["payload"]["access_token"]


class TestSendMail:
    """发送邮件测试 (M-001)"""

    @pytest.mark.asyncio
    async def test_send_mail_success(self, client):
        """本域发送成功"""
        token = await register_and_login(client, "sender1")
        # 注册收件人
        await register_and_login(client, "receiver1")

        resp = await client.request(Action.SEND_MAIL, {
            "to": ["receiver1@alpha.local"],
            "subject": "测试邮件",
            "body": "这是一封测试邮件"
        }, token=token)

        assert resp["status"] == StatusCode.OK
        assert "email_id" in resp["payload"]
        assert resp["payload"]["from"] == "sender1@alpha.local"

    @pytest.mark.asyncio
    async def test_send_mail_no_recipient(self, client):
        """无收件人"""
        token = await register_and_login(client, "sender2")
        resp = await client.request(Action.SEND_MAIL, {
            "to": [],
            "subject": "空收件人",
            "body": "test"
        }, token=token)
        assert resp["status"] == StatusCode.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_send_mail_without_auth(self, client):
        """未认证发送"""
        resp = await client.request(Action.SEND_MAIL, {
            "to": ["someone@alpha.local"],
            "subject": "test",
            "body": "test"
        })
        assert resp["status"] == StatusCode.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_send_mail_multiple_recipients(self, client):
        """群发多人 (M-005)"""
        token = await register_and_login(client, "group_sender")
        await register_and_login(client, "recv_a")
        await register_and_login(client, "recv_b")
        await register_and_login(client, "recv_c")

        resp = await client.request(Action.SEND_MAIL, {
            "to": ["recv_a@alpha.local", "recv_b@alpha.local", "recv_c@alpha.local"],
            "subject": "群发测试",
            "body": "这是群发邮件"
        }, token=token)

        assert resp["status"] == StatusCode.OK
        assert len(resp["payload"]["to"]) == 3


class TestInbox:
    """收件箱测试 (M-002)"""

    @pytest.mark.asyncio
    async def test_list_inbox(self, client):
        """收件箱列表"""
        sender_token = await register_and_login(client, "inbox_sender")
        receiver_token = await register_and_login(client, "inbox_receiver")

        # 发送邮件
        await client.request(Action.SEND_MAIL, {
            "to": ["inbox_receiver@alpha.local"],
            "subject": "收件箱测试",
            "body": "测试内容"
        }, token=sender_token)

        # 查看收件箱
        resp = await client.request(Action.LIST_INBOX, {}, token=receiver_token)
        assert resp["status"] == StatusCode.OK
        assert resp["payload"]["total"] >= 1
        assert len(resp["payload"]["emails"]) >= 1

    @pytest.mark.asyncio
    async def test_read_mail(self, client):
        """阅读邮件+标记已读"""
        sender_token = await register_and_login(client, "read_sender")
        receiver_token = await register_and_login(client, "read_receiver")

        # 发送
        send_resp = await client.request(Action.SEND_MAIL, {
            "to": ["read_receiver@alpha.local"],
            "subject": "阅读测试",
            "body": "测试内容详情"
        }, token=sender_token)
        email_id = send_resp["payload"]["email_id"]

        # 阅读
        resp = await client.request(Action.READ_MAIL, {
            "email_id": email_id
        }, token=receiver_token)

        assert resp["status"] == StatusCode.OK
        assert resp["payload"]["subject"] == "阅读测试"
        assert resp["payload"]["body"] == "测试内容详情"

    @pytest.mark.asyncio
    async def test_read_mail_forbidden(self, client):
        """无权查看他人邮件"""
        sender_token = await register_and_login(client, "priv_sender")
        await register_and_login(client, "priv_receiver")
        other_token = await register_and_login(client, "priv_other")

        send_resp = await client.request(Action.SEND_MAIL, {
            "to": ["priv_receiver@alpha.local"],
            "subject": "隐私测试",
            "body": "机密"
        }, token=sender_token)
        email_id = send_resp["payload"]["email_id"]

        # 第三方试图阅读
        resp = await client.request(Action.READ_MAIL, {
            "email_id": email_id
        }, token=other_token)
        assert resp["status"] == StatusCode.FORBIDDEN


class TestSentBox:
    """发件箱测试 (M-003)"""

    @pytest.mark.asyncio
    async def test_list_sent(self, client):
        """发件箱记录完整"""
        token = await register_and_login(client, "sent_user")
        await register_and_login(client, "sent_recv")

        await client.request(Action.SEND_MAIL, {
            "to": ["sent_recv@alpha.local"],
            "subject": "发件箱测试1",
            "body": "内容1"
        }, token=token)
        await client.request(Action.SEND_MAIL, {
            "to": ["sent_recv@alpha.local"],
            "subject": "发件箱测试2",
            "body": "内容2"
        }, token=token)

        resp = await client.request(Action.LIST_SENT, {}, token=token)
        assert resp["status"] == StatusCode.OK
        assert len(resp["payload"]["emails"]) >= 2


class TestDraft:
    """草稿箱测试 (M-004)"""

    @pytest.mark.asyncio
    async def test_save_and_list_draft(self, client):
        """保存和查看草稿"""
        token = await register_and_login(client, "draft_user")

        # 保存草稿
        resp = await client.request(Action.SAVE_DRAFT, {
            "to": ["someone@alpha.local"],
            "subject": "草稿主题",
            "body": "草稿内容"
        }, token=token)
        assert resp["status"] == StatusCode.OK
        draft_id = resp["payload"]["draft_id"]

        # 列出草稿
        resp = await client.request(Action.LIST_DRAFTS, {}, token=token)
        assert resp["status"] == StatusCode.OK
        assert len(resp["payload"]["drafts"]) >= 1
        assert any(d["email_id"] == draft_id for d in resp["payload"]["drafts"])

    @pytest.mark.asyncio
    async def test_update_draft(self, client):
        """更新草稿"""
        token = await register_and_login(client, "draft_upd")

        # 创建草稿
        resp = await client.request(Action.SAVE_DRAFT, {
            "to": ["a@alpha.local"],
            "subject": "原始主题",
            "body": "原始内容"
        }, token=token)
        draft_id = resp["payload"]["draft_id"]

        # 更新草稿
        resp = await client.request(Action.SAVE_DRAFT, {
            "draft_id": draft_id,
            "to": ["b@alpha.local"],
            "subject": "更新主题",
            "body": "更新内容"
        }, token=token)
        assert resp["status"] == StatusCode.OK
        assert resp["payload"]["draft_id"] == draft_id


class TestRecall:
    """邮件撤回测试 (M-007)"""

    @pytest.mark.asyncio
    async def test_recall_success(self, client, mail_config):
        """正常撤回"""
        token = await register_and_login(client, "recall_sender")
        await register_and_login(client, "recall_recv")

        # 发送
        send_resp = await client.request(Action.SEND_MAIL, {
            "to": ["recall_recv@alpha.local"],
            "subject": "撤回测试",
            "body": "这封邮件将被撤回"
        }, token=token)
        email_id = send_resp["payload"]["email_id"]

        # 计算撤回签名
        signature = compute_hmac(
            mail_config.security.jwt_secret,
            f"RECALL:{email_id}:recall_sender@alpha.local"
        )

        # 撤回
        resp = await client.request(Action.RECALL_MAIL, {
            "email_id": email_id,
            "signature": signature
        }, token=token)
        assert resp["status"] == StatusCode.OK
        assert "撤回成功" in resp["message"]

    @pytest.mark.asyncio
    async def test_recall_not_sender(self, client, mail_config):
        """非发件人不能撤回"""
        sender_token = await register_and_login(client, "recall_s2")
        recv_token = await register_and_login(client, "recall_r2")

        send_resp = await client.request(Action.SEND_MAIL, {
            "to": ["recall_r2@alpha.local"],
            "subject": "撤回权限测试",
            "body": "test"
        }, token=sender_token)
        email_id = send_resp["payload"]["email_id"]

        # 收件人尝试撤回
        signature = compute_hmac(
            mail_config.security.jwt_secret,
            f"RECALL:{email_id}:recall_r2@alpha.local"
        )
        resp = await client.request(Action.RECALL_MAIL, {
            "email_id": email_id,
            "signature": signature
        }, token=recv_token)
        assert resp["status"] == StatusCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_recall_invalid_signature(self, client):
        """伪造签名撤回被拒绝"""
        token = await register_and_login(client, "recall_s3")
        await register_and_login(client, "recall_r3")

        send_resp = await client.request(Action.SEND_MAIL, {
            "to": ["recall_r3@alpha.local"],
            "subject": "签名测试",
            "body": "test"
        }, token=token)
        email_id = send_resp["payload"]["email_id"]

        # 伪造签名
        resp = await client.request(Action.RECALL_MAIL, {
            "email_id": email_id,
            "signature": "fake-signature"
        }, token=token)
        assert resp["status"] == StatusCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_recall_idempotent(self, client, mail_config):
        """重复撤回幂等"""
        token = await register_and_login(client, "recall_s4")
        await register_and_login(client, "recall_r4")

        send_resp = await client.request(Action.SEND_MAIL, {
            "to": ["recall_r4@alpha.local"],
            "subject": "幂等测试",
            "body": "test"
        }, token=token)
        email_id = send_resp["payload"]["email_id"]

        signature = compute_hmac(
            mail_config.security.jwt_secret,
            f"RECALL:{email_id}:recall_s4@alpha.local"
        )

        # 第一次撤回
        resp = await client.request(Action.RECALL_MAIL, {
            "email_id": email_id,
            "signature": signature
        }, token=token)
        assert resp["status"] == StatusCode.OK

        # 重复撤回
        resp = await client.request(Action.RECALL_MAIL, {
            "email_id": email_id,
            "signature": signature
        }, token=token)
        assert resp["status"] == StatusCode.OK
        assert "重复" in resp["message"]


class TestGroup:
    """群组测试 (M-006)"""

    @pytest.mark.asyncio
    async def test_create_group(self, client):
        """创建群组"""
        token = await register_and_login(client, "grp_owner")
        await register_and_login(client, "grp_m1")
        await register_and_login(client, "grp_m2")

        resp = await client.request(Action.CREATE_GROUP, {
            "group_name": "测试群组",
            "members": ["grp_m1", "grp_m2"]
        }, token=token)

        assert resp["status"] == StatusCode.CREATED
        assert resp["payload"]["group_name"] == "测试群组"
        assert len(resp["payload"]["members"]) == 2

    @pytest.mark.asyncio
    async def test_list_groups(self, client):
        """列出群组"""
        token = await register_and_login(client, "grp_list_owner")

        await client.request(Action.CREATE_GROUP, {
            "group_name": "群组A",
            "members": ["user_a@alpha.local"]
        }, token=token)

        resp = await client.request(Action.LIST_GROUPS, {}, token=token)
        assert resp["status"] == StatusCode.OK
        assert len(resp["payload"]["groups"]) >= 1
