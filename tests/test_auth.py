"""
M2 用户认证体系测试 - 注册/登录/登出/Token管理/防暴力破解
"""
import asyncio
import pytest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.protocol import Action, StatusCode, build_request
from server.main import EmailServer
from server.config import ServerConfig
from client.connection import Connection


@pytest.fixture
def auth_config():
    """认证测试服务器配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18010
    config.data_dir = "./data/test_auth"
    config.security.jwt_secret = "test-jwt-secret"
    config.security.bcrypt_cost = 4  # 测试时降低 cost 加速
    config.security.max_login_attempts_ip = 5
    config.security.ip_lockout_minutes = 15
    config.security.max_login_attempts_account = 10
    config.security.account_lockout_minutes = 30
    return config


@pytest.fixture
async def auth_server(auth_config):
    """启动认证测试服务器"""
    # 清理旧测试数据
    db_path = os.path.join(auth_config.data_dir, "safeemail.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    
    server = EmailServer(auth_config)
    os.makedirs(auth_config.data_dir, exist_ok=True)
    await server._init_services()
    
    srv = await asyncio.start_server(
        server.handler.handle_connection,
        auth_config.host,
        auth_config.port
    )
    yield srv, server
    srv.close()
    await srv.wait_closed()
    await server.db.close()


@pytest.fixture
async def client(auth_config, auth_server):
    """创建连接到测试服务器的客户端"""
    conn = Connection(auth_config.host, auth_config.port)
    await conn.connect()
    yield conn
    await conn.close()


class TestRegister:
    """注册功能测试 (U-001)"""

    @pytest.mark.asyncio
    async def test_register_success(self, client):
        """正常注册"""
        resp = await client.request(Action.REGISTER, {
            "username": "testuser",
            "password": "TestPass123"
        })
        assert resp["status"] == StatusCode.CREATED
        assert resp["message"] == "注册成功"
        assert "user_id" in resp["payload"]
        assert resp["payload"]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client):
        """重复用户名注册"""
        # 先注册
        await client.request(Action.REGISTER, {
            "username": "duplicate",
            "password": "TestPass123"
        })
        # 再次注册同名
        resp = await client.request(Action.REGISTER, {
            "username": "duplicate",
            "password": "TestPass456"
        })
        assert resp["status"] == StatusCode.CONFLICT
        assert "已存在" in resp["message"]

    @pytest.mark.asyncio
    async def test_register_weak_password_short(self, client):
        """弱密码 - 过短"""
        resp = await client.request(Action.REGISTER, {
            "username": "weakuser1",
            "password": "Abc1"
        })
        assert resp["status"] == StatusCode.BAD_REQUEST
        assert "8位" in resp["message"]

    @pytest.mark.asyncio
    async def test_register_weak_password_no_upper(self, client):
        """弱密码 - 无大写"""
        resp = await client.request(Action.REGISTER, {
            "username": "weakuser2",
            "password": "testpass123"
        })
        assert resp["status"] == StatusCode.BAD_REQUEST
        assert "大写" in resp["message"]

    @pytest.mark.asyncio
    async def test_register_weak_password_no_digit(self, client):
        """弱密码 - 无数字"""
        resp = await client.request(Action.REGISTER, {
            "username": "weakuser3",
            "password": "TestPassword"
        })
        assert resp["status"] == StatusCode.BAD_REQUEST
        assert "数字" in resp["message"]

    @pytest.mark.asyncio
    async def test_register_short_username(self, client):
        """用户名太短"""
        resp = await client.request(Action.REGISTER, {
            "username": "ab",
            "password": "TestPass123"
        })
        assert resp["status"] == StatusCode.BAD_REQUEST


class TestLogin:
    """登录功能测试 (U-002)"""

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """正确登录"""
        # 先注册
        await client.request(Action.REGISTER, {
            "username": "loginuser",
            "password": "LoginPass123"
        })
        # 登录
        resp = await client.request(Action.LOGIN, {
            "username": "loginuser",
            "password": "LoginPass123"
        })
        assert resp["status"] == StatusCode.OK
        assert "access_token" in resp["payload"]
        assert "refresh_token" in resp["payload"]
        assert resp["payload"]["username"] == "loginuser"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        """错误密码"""
        # 先注册
        await client.request(Action.REGISTER, {
            "username": "wrongpwd",
            "password": "CorrectPass123"
        })
        # 错误密码登录
        resp = await client.request(Action.LOGIN, {
            "username": "wrongpwd",
            "password": "WrongPass123"
        })
        assert resp["status"] == StatusCode.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """不存在的用户"""
        resp = await client.request(Action.LOGIN, {
            "username": "noexist",
            "password": "SomePass123"
        })
        assert resp["status"] == StatusCode.UNAUTHORIZED


class TestSession:
    """会话管理测试 (U-003)"""

    @pytest.mark.asyncio
    async def test_token_refresh(self, client):
        """Token 续期"""
        # 注册+登录
        await client.request(Action.REGISTER, {
            "username": "refreshuser",
            "password": "RefreshPass123"
        })
        login_resp = await client.request(Action.LOGIN, {
            "username": "refreshuser",
            "password": "RefreshPass123"
        })
        refresh_token = login_resp["payload"]["refresh_token"]
        
        # 续期
        resp = await client.request(Action.REFRESH, {
            "refresh_token": refresh_token
        })
        assert resp["status"] == StatusCode.OK
        assert "access_token" in resp["payload"]

    @pytest.mark.asyncio
    async def test_invalid_refresh_token(self, client):
        """无效 Refresh Token"""
        resp = await client.request(Action.REFRESH, {
            "refresh_token": "invalid.token.here"
        })
        assert resp["status"] == StatusCode.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_forged_token_rejected(self, client):
        """伪造 Token 被拒绝"""
        # 尝试用伪造 token 执行操作
        msg = build_request(Action.LOGOUT, token="forged.invalid.token")
        await client.send(msg)
        resp = await client.receive()
        assert resp["status"] == StatusCode.UNAUTHORIZED


class TestLogout:
    """登出功能测试 (U-004)"""

    @pytest.mark.asyncio
    async def test_logout_success(self, client):
        """正常登出"""
        # 注册+登录
        await client.request(Action.REGISTER, {
            "username": "logoutuser",
            "password": "LogoutPass123"
        })
        login_resp = await client.request(Action.LOGIN, {
            "username": "logoutuser",
            "password": "LogoutPass123"
        })
        access_token = login_resp["payload"]["access_token"]
        
        # 登出
        msg = build_request(Action.LOGOUT, token=access_token)
        await client.send(msg)
        resp = await client.receive()
        assert resp["status"] == StatusCode.OK

    @pytest.mark.asyncio
    async def test_token_not_reusable_after_logout(self, client):
        """登出后 Token 不可复用"""
        # 注册+登录
        await client.request(Action.REGISTER, {
            "username": "reuseuser",
            "password": "ReusePass123"
        })
        login_resp = await client.request(Action.LOGIN, {
            "username": "reuseuser",
            "password": "ReusePass123"
        })
        access_token = login_resp["payload"]["access_token"]
        
        # 登出
        msg = build_request(Action.LOGOUT, token=access_token)
        await client.send(msg)
        await client.receive()
        
        # 尝试使用已登出的 Token
        msg = build_request(Action.LOGOUT, token=access_token)
        await client.send(msg)
        resp = await client.receive()
        assert resp["status"] == StatusCode.UNAUTHORIZED


class TestRateLimit:
    """防暴力破解测试 (SEC)"""

    @pytest.mark.asyncio
    async def test_ip_lockout_after_failures(self, client):
        """IP 多次失败后锁定"""
        # 注册一个用户
        await client.request(Action.REGISTER, {
            "username": "rateuser",
            "password": "RatePass123"
        })
        
        # 连续失败登录 5 次
        for i in range(5):
            await client.request(Action.LOGIN, {
                "username": "rateuser",
                "password": "WrongPass000"
            })
        
        # 第 6 次应该被限流
        resp = await client.request(Action.LOGIN, {
            "username": "rateuser",
            "password": "WrongPass000"
        })
        assert resp["status"] == StatusCode.TOO_MANY_REQUESTS

    @pytest.mark.asyncio
    async def test_captcha_after_3_failures(self, client):
        """3 次失败后触发验证码"""
        await client.request(Action.REGISTER, {
            "username": "captchauser",
            "password": "CaptchaPass123"
        })
        
        # 连续失败 3 次
        for i in range(3):
            resp = await client.request(Action.LOGIN, {
                "username": "captchauser",
                "password": "WrongPass000"
            })
        
        # 第 4 次应该带验证码提示
        resp = await client.request(Action.LOGIN, {
            "username": "captchauser",
            "password": "WrongPass000"
        })
        # 注意：captcha 是在第3次失败后的响应中出现
        # 由于我们的 ip 已经有3次记录了，所以第4次应该也需要 captcha
        assert resp["status"] == StatusCode.UNAUTHORIZED
        assert resp["payload"].get("captcha_required") == True
        assert "captcha_question" in resp["payload"]
