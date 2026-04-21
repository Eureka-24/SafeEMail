"""
M9 并发与稳定性测试 - TC-010/TC-011
"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "alpha.env")
load_dotenv(_env_path, override=True)

from shared.protocol import Action, StatusCode
from server.main import EmailServer
from server.config import ServerConfig
from client.connection import Connection


@pytest.fixture
def conc_config():
    """并发测试服务器配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18090
    config.data_dir = "./data/test_concurrent"
    config.security.jwt_secret = "test-jwt-secret-conc"
    config.security.bcrypt_cost = 4
    config.security.max_send_per_minute = 200
    config.security.max_send_per_hour = 1000
    return config


@pytest.fixture
async def conc_server(conc_config):
    """启动测试服务器"""
    db_path = os.path.join(conc_config.data_dir, "safeemail.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    server = EmailServer(conc_config)
    os.makedirs(conc_config.data_dir, exist_ok=True)
    await server._init_services()

    srv = await asyncio.start_server(
        server.handler.handle_connection,
        conc_config.host,
        conc_config.port
    )
    yield srv, server
    srv.close()
    await srv.wait_closed()
    await server.db.close()


async def create_client(host, port):
    """创建并连接客户端"""
    conn = Connection(host, port)
    await conn.connect()
    return conn


async def register_and_login(conn, username, password="TestPass123"):
    """辅助：注册并登录"""
    await conn.request(Action.REGISTER, {"username": username, "password": password})
    resp = await conn.request(Action.LOGIN, {"username": username, "password": password})
    return resp["payload"]["access_token"]


class TestConcurrentClients:
    """TC-010: 20 客户端并发收发测试"""

    @pytest.mark.asyncio
    async def test_20_concurrent_send(self, conc_server, conc_config):
        """TC-010: 20个客户端同时发送邮件"""
        _, server = conc_server
        host, port = conc_config.host, conc_config.port

        # 先用一个连接注册所有用户和一个接收者
        setup_conn = await create_client(host, port)
        try:
            await setup_conn.request(Action.REGISTER, {
                "username": "conc_recv", "password": "TestPass123"
            })
            for i in range(20):
                await setup_conn.request(Action.REGISTER, {
                    "username": f"conc_user{i}", "password": "TestPass123"
                })
        finally:
            await setup_conn.close()

        # 20 个客户端并发连接并发送
        async def send_mail(user_index):
            conn = await create_client(host, port)
            try:
                resp = await conn.request(Action.LOGIN, {
                    "username": f"conc_user{user_index}", "password": "TestPass123"
                })
                token = resp["payload"]["access_token"]
                
                send_resp = await conn.request(Action.SEND_MAIL, {
                    "to": ["conc_recv@alpha.local"],
                    "subject": f"并发测试 {user_index}",
                    "body": f"来自用户 {user_index} 的并发邮件"
                }, token=token)
                return send_resp["status"]
            finally:
                await conn.close()

        # 并发执行
        results = await asyncio.gather(*[send_mail(i) for i in range(20)])
        
        # 所有发送都应成功
        assert all(r == StatusCode.OK for r in results), f"失败的请求: {[r for r in results if r != StatusCode.OK]}"

        # 验证收件人确实收到了 20 封邮件
        verify_conn = await create_client(host, port)
        try:
            resp = await verify_conn.request(Action.LOGIN, {
                "username": "conc_recv", "password": "TestPass123"
            })
            token = resp["payload"]["access_token"]
            inbox = await verify_conn.request(Action.LIST_INBOX, {
                "page_size": 50
            }, token=token)
            assert inbox["payload"]["total"] == 20
        finally:
            await verify_conn.close()

    @pytest.mark.asyncio
    async def test_concurrent_read_write(self, conc_server, conc_config):
        """并发读写不冲突"""
        _, server = conc_server
        host, port = conc_config.host, conc_config.port

        setup_conn = await create_client(host, port)
        try:
            await setup_conn.request(Action.REGISTER, {
                "username": "rw_sender", "password": "TestPass123"
            })
            await setup_conn.request(Action.REGISTER, {
                "username": "rw_reader", "password": "TestPass123"
            })
            # 先发几封邮件
            resp = await setup_conn.request(Action.LOGIN, {
                "username": "rw_sender", "password": "TestPass123"
            })
            token = resp["payload"]["access_token"]
            for i in range(5):
                await setup_conn.request(Action.SEND_MAIL, {
                    "to": ["rw_reader@alpha.local"],
                    "subject": f"读写测试 {i}",
                    "body": f"内容 {i}"
                }, token=token)
        finally:
            await setup_conn.close()

        # 并发：一半客户端发送新邮件，一半客户端读取收件箱
        async def send_task(idx):
            conn = await create_client(host, port)
            try:
                resp = await conn.request(Action.LOGIN, {
                    "username": "rw_sender", "password": "TestPass123"
                })
                token = resp["payload"]["access_token"]
                r = await conn.request(Action.SEND_MAIL, {
                    "to": ["rw_reader@alpha.local"],
                    "subject": f"并发新邮件 {idx}",
                    "body": "并发写入"
                }, token=token)
                return r["status"]
            finally:
                await conn.close()

        async def read_task():
            conn = await create_client(host, port)
            try:
                resp = await conn.request(Action.LOGIN, {
                    "username": "rw_reader", "password": "TestPass123"
                })
                token = resp["payload"]["access_token"]
                r = await conn.request(Action.LIST_INBOX, {}, token=token)
                return r["status"]
            finally:
                await conn.close()

        tasks = [send_task(i) for i in range(5)] + [read_task() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        assert all(r == StatusCode.OK for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_connections_stability(self, conc_server, conc_config):
        """多个连接同时执行 PING 不崩溃"""
        host, port = conc_config.host, conc_config.port

        async def ping_task():
            conn = await create_client(host, port)
            try:
                resp = await conn.request(Action.PING)
                return resp["status"]
            finally:
                await conn.close()

        results = await asyncio.gather(*[ping_task() for _ in range(20)])
        assert all(r == StatusCode.OK for r in results)


class TestHighFrequencySending:
    """TC-011: 高频发送压力测试"""

    @pytest.mark.asyncio
    async def test_burst_sending(self, conc_server, conc_config):
        """TC-011: 单用户快速连续发送多封邮件"""
        host, port = conc_config.host, conc_config.port

        conn = await create_client(host, port)
        try:
            await conn.request(Action.REGISTER, {
                "username": "burst_sender", "password": "TestPass123"
            })
            await conn.request(Action.REGISTER, {
                "username": "burst_recv", "password": "TestPass123"
            })
            resp = await conn.request(Action.LOGIN, {
                "username": "burst_sender", "password": "TestPass123"
            })
            token = resp["payload"]["access_token"]

            # 快速发送 30 封邮件
            success_count = 0
            for i in range(30):
                r = await conn.request(Action.SEND_MAIL, {
                    "to": ["burst_recv@alpha.local"],
                    "subject": f"Burst {i}",
                    "body": f"High frequency test {i}"
                }, token=token)
                if r["status"] == StatusCode.OK:
                    success_count += 1

            # 至少大部分应该成功
            assert success_count >= 25, f"只有 {success_count}/30 封成功"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_parallel_burst_different_users(self, conc_server, conc_config):
        """多用户并行高频发送"""
        host, port = conc_config.host, conc_config.port

        # 注册用户
        setup_conn = await create_client(host, port)
        try:
            await setup_conn.request(Action.REGISTER, {
                "username": "burst_target", "password": "TestPass123"
            })
            for i in range(5):
                await setup_conn.request(Action.REGISTER, {
                    "username": f"burst_u{i}", "password": "TestPass123"
                })
        finally:
            await setup_conn.close()

        async def user_burst(user_idx, count=10):
            conn = await create_client(host, port)
            try:
                resp = await conn.request(Action.LOGIN, {
                    "username": f"burst_u{user_idx}", "password": "TestPass123"
                })
                token = resp["payload"]["access_token"]
                ok = 0
                for i in range(count):
                    r = await conn.request(Action.SEND_MAIL, {
                        "to": ["burst_target@alpha.local"],
                        "subject": f"Burst u{user_idx}-{i}",
                        "body": "test"
                    }, token=token)
                    if r["status"] == StatusCode.OK:
                        ok += 1
                return ok
            finally:
                await conn.close()

        results = await asyncio.gather(*[user_burst(i) for i in range(5)])
        # 每个用户至少 8/10 成功
        for i, ok_count in enumerate(results):
            assert ok_count >= 8, f"用户 burst_u{i} 只有 {ok_count}/10 成功"
