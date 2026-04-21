"""
M1 基础框架测试 - PING/PONG 端到端测试 + 双端口验证
"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.protocol import Action, StatusCode, build_request
from server.main import EmailServer
from server.config import ServerConfig
from client.connection import Connection


@pytest.fixture
def alpha_config():
    """Alpha 服务器配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18001  # 测试使用不同端口
    config.data_dir = "./data/test_alpha"
    return config


@pytest.fixture
def beta_config():
    """Beta 服务器配置"""
    config = ServerConfig()
    config.domain = "beta.local"
    config.host = "127.0.0.1"
    config.port = 18002
    config.data_dir = "./data/test_beta"
    return config


@pytest.fixture
async def alpha_server(alpha_config):
    """启动 Alpha 测试服务器"""
    server = EmailServer(alpha_config)
    os.makedirs(alpha_config.data_dir, exist_ok=True)
    
    srv = await asyncio.start_server(
        server.handler.handle_connection,
        alpha_config.host,
        alpha_config.port
    )
    yield srv
    srv.close()
    await srv.wait_closed()


@pytest.fixture
async def beta_server(beta_config):
    """启动 Beta 测试服务器"""
    server = EmailServer(beta_config)
    os.makedirs(beta_config.data_dir, exist_ok=True)
    
    srv = await asyncio.start_server(
        server.handler.handle_connection,
        beta_config.host,
        beta_config.port
    )
    yield srv
    srv.close()
    await srv.wait_closed()


class TestPingPong:
    """PING/PONG 端到端测试"""

    @pytest.mark.asyncio
    async def test_ping_pong_alpha(self, alpha_server, alpha_config):
        """测试 Alpha 服务器 PING/PONG"""
        conn = Connection(alpha_config.host, alpha_config.port)
        await conn.connect()
        
        try:
            response = await conn.request(Action.PING)
            assert response["status"] == StatusCode.OK
            assert response["message"] == "PONG"
            assert response["payload"]["action"] == Action.PONG
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_ping_pong_beta(self, beta_server, beta_config):
        """测试 Beta 服务器 PING/PONG"""
        conn = Connection(beta_config.host, beta_config.port)
        await conn.connect()
        
        try:
            response = await conn.request(Action.PING)
            assert response["status"] == StatusCode.OK
            assert response["message"] == "PONG"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_dual_server_isolation(self, alpha_server, beta_server, alpha_config, beta_config):
        """测试双服务器互不干扰"""
        conn_alpha = Connection(alpha_config.host, alpha_config.port)
        conn_beta = Connection(beta_config.host, beta_config.port)
        
        await conn_alpha.connect()
        await conn_beta.connect()
        
        try:
            # 同时向两个服务器发送 PING
            resp_alpha = await conn_alpha.request(Action.PING)
            resp_beta = await conn_beta.request(Action.PING)
            
            assert resp_alpha["status"] == StatusCode.OK
            assert resp_beta["status"] == StatusCode.OK
        finally:
            await conn_alpha.close()
            await conn_beta.close()

    @pytest.mark.asyncio
    async def test_unknown_action(self, alpha_server, alpha_config):
        """测试未知 action 返回错误"""
        conn = Connection(alpha_config.host, alpha_config.port)
        await conn.connect()
        
        try:
            response = await conn.request("UNKNOWN_ACTION")
            assert response["status"] == StatusCode.BAD_REQUEST
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_multiple_messages(self, alpha_server, alpha_config):
        """测试连续发送多条消息"""
        conn = Connection(alpha_config.host, alpha_config.port)
        await conn.connect()
        
        try:
            for i in range(5):
                response = await conn.request(Action.PING)
                assert response["status"] == StatusCode.OK
                assert response["message"] == "PONG"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, alpha_server, alpha_config):
        """测试多个并发连接"""
        connections = []
        
        try:
            for _ in range(5):
                conn = Connection(alpha_config.host, alpha_config.port)
                await conn.connect()
                connections.append(conn)
            
            # 所有连接同时发送 PING
            tasks = [conn.request(Action.PING) for conn in connections]
            responses = await asyncio.gather(*tasks)
            
            for resp in responses:
                assert resp["status"] == StatusCode.OK
        finally:
            for conn in connections:
                await conn.close()


class TestProtocol:
    """协议层测试"""

    @pytest.mark.asyncio
    async def test_message_format(self, alpha_server, alpha_config):
        """测试响应消息格式完整性"""
        conn = Connection(alpha_config.host, alpha_config.port)
        await conn.connect()
        
        try:
            response = await conn.request(Action.PING)
            # 验证响应包含必要字段
            assert "version" in response
            assert "type" in response
            assert "request_id" in response
            assert "status" in response
            assert "message" in response
            assert "payload" in response
            assert response["version"] == "1.0"
            assert response["type"] == "RESPONSE"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_invalid_message_type(self, alpha_server, alpha_config):
        """测试无效消息类型"""
        conn = Connection(alpha_config.host, alpha_config.port)
        await conn.connect()
        
        try:
            # 发送一个 type 无效的消息
            msg = {
                "version": "1.0",
                "type": "INVALID",
                "action": "PING",
                "request_id": "test-123",
                "token": None,
                "payload": {}
            }
            await conn.send(msg)
            response = await conn.receive()
            assert response["status"] == StatusCode.BAD_REQUEST
        finally:
            await conn.close()
