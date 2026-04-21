"""
M1 TLS 通信测试 - 验证 TLS 加密连接功能
"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.protocol import Action, StatusCode
from server.main import EmailServer
from server.config import ServerConfig
from server.security.tls import create_server_ssl_context, create_client_ssl_context
from client.connection import Connection

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CERTS_DIR = os.path.join(ROOT_DIR, "certs")


@pytest.fixture
def tls_server_config():
    """带 TLS 的 Alpha 服务器配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18003
    config.data_dir = "./data/test_tls_alpha"
    config.tls.cert_file = os.path.join(CERTS_DIR, "alpha.local.crt")
    config.tls.key_file = os.path.join(CERTS_DIR, "alpha.local.key")
    config.tls.ca_file = os.path.join(CERTS_DIR, "ca.crt")
    return config


@pytest.fixture
async def tls_server(tls_server_config):
    """启动带 TLS 的测试服务器"""
    server = EmailServer(tls_server_config)
    os.makedirs(tls_server_config.data_dir, exist_ok=True)

    ssl_ctx = create_server_ssl_context(
        tls_server_config.tls.cert_file,
        tls_server_config.tls.key_file,
        tls_server_config.tls.ca_file
    )

    srv = await asyncio.start_server(
        server.handler.handle_connection,
        tls_server_config.host,
        tls_server_config.port,
        ssl=ssl_ctx
    )
    yield srv
    srv.close()
    await srv.wait_closed()


class TestTLS:
    """TLS 加密通信测试"""

    @pytest.mark.asyncio
    async def test_tls_ping_pong(self, tls_server, tls_server_config):
        """测试 TLS 加密连接下的 PING/PONG"""
        ssl_ctx = create_client_ssl_context(
            ca_file=os.path.join(CERTS_DIR, "ca.crt")
        )
        
        conn = Connection(tls_server_config.host, tls_server_config.port)
        await conn.connect(use_tls=True, ssl_context=ssl_ctx)
        
        try:
            response = await conn.request(Action.PING)
            assert response["status"] == StatusCode.OK
            assert response["message"] == "PONG"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_tls_multiple_messages(self, tls_server, tls_server_config):
        """测试 TLS 连接下连续消息"""
        ssl_ctx = create_client_ssl_context(
            ca_file=os.path.join(CERTS_DIR, "ca.crt")
        )
        
        conn = Connection(tls_server_config.host, tls_server_config.port)
        await conn.connect(use_tls=True, ssl_context=ssl_ctx)
        
        try:
            for i in range(3):
                response = await conn.request(Action.PING)
                assert response["status"] == StatusCode.OK
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_tls_reject_plain_connection(self, tls_server, tls_server_config):
        """测试非 TLS 连接被拒绝"""
        conn = Connection(tls_server_config.host, tls_server_config.port)
        
        # 尝试以明文连接 TLS 服务器应该失败
        await conn.connect(use_tls=False)
        try:
            with pytest.raises(Exception):
                await conn.request(Action.PING)
        finally:
            try:
                await conn.close()
            except Exception:
                pass
