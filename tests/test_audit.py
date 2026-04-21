"""
M9 审计日志验证测试 - 验证关键操作的审计日志记录
"""
import asyncio
import json
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "alpha.env")
load_dotenv(_env_path, override=True)

from shared.protocol import Action, StatusCode
from shared.crypto import compute_hmac
from server.main import EmailServer
from server.config import ServerConfig
from server.audit.logger import AuditLogger
from client.connection import Connection


@pytest.fixture
def audit_config():
    """审计测试配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18095
    config.data_dir = "./data/test_audit"
    config.security.jwt_secret = "test-jwt-secret-audit"
    config.security.bcrypt_cost = 4
    config.security.max_send_per_minute = 5
    config.security.max_send_per_hour = 200
    return config


@pytest.fixture
async def audit_server(audit_config):
    """启动测试服务器"""
    db_path = os.path.join(audit_config.data_dir, "safeemail.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    server = EmailServer(audit_config)
    os.makedirs(audit_config.data_dir, exist_ok=True)
    await server._init_services()

    srv = await asyncio.start_server(
        server.handler.handle_connection,
        audit_config.host,
        audit_config.port
    )
    yield srv, server
    srv.close()
    await srv.wait_closed()
    await server.db.close()


@pytest.fixture
async def client(audit_config, audit_server):
    """客户端连接"""
    conn = Connection(audit_config.host, audit_config.port)
    await conn.connect()
    yield conn
    await conn.close()


async def register_and_login(client, username, password="TestPass123"):
    """辅助"""
    await client.request(Action.REGISTER, {"username": username, "password": password})
    resp = await client.request(Action.LOGIN, {"username": username, "password": password})
    return resp["payload"]["access_token"]


class TestAuditLogging:
    """审计日志记录验证"""

    @pytest.mark.asyncio
    async def test_register_audit_log(self, client, audit_server, audit_config):
        """注册操作产生审计日志"""
        _, server = audit_server
        audit = AuditLogger(server.db)

        await client.request(Action.REGISTER, {
            "username": "audit_reg_user", "password": "TestPass123"
        })

        logs = await audit.query_logs(action="REGISTER", user_id="audit_reg_user")
        assert len(logs) >= 1
        log = logs[0]
        assert log["action"] == "REGISTER"
        assert log["user_id"] == "audit_reg_user"
        assert log["level"] == "INFO"
        detail = json.loads(log["detail"])
        assert detail["success"] is True

    @pytest.mark.asyncio
    async def test_login_success_audit_log(self, client, audit_server, audit_config):
        """登录成功产生审计日志"""
        _, server = audit_server
        audit = AuditLogger(server.db)

        await client.request(Action.REGISTER, {
            "username": "audit_login_user", "password": "TestPass123"
        })
        await client.request(Action.LOGIN, {
            "username": "audit_login_user", "password": "TestPass123"
        })

        logs = await audit.query_logs(action="LOGIN", user_id="audit_login_user")
        success_logs = [l for l in logs if json.loads(l["detail"])["success"] is True]
        assert len(success_logs) >= 1
        assert success_logs[0]["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_login_failure_audit_log(self, client, audit_server, audit_config):
        """登录失败产生 WARN 级别审计日志"""
        _, server = audit_server
        audit = AuditLogger(server.db)

        await client.request(Action.REGISTER, {
            "username": "audit_fail_user", "password": "TestPass123"
        })
        await client.request(Action.LOGIN, {
            "username": "audit_fail_user", "password": "WrongPass000"
        })

        logs = await audit.query_logs(action="LOGIN", user_id="audit_fail_user")
        fail_logs = [l for l in logs if json.loads(l["detail"])["success"] is False]
        assert len(fail_logs) >= 1
        assert fail_logs[0]["level"] == "WARN"
        detail = json.loads(fail_logs[0]["detail"])
        assert detail["reason"] == "密码错误"

    @pytest.mark.asyncio
    async def test_send_mail_audit_log(self, client, audit_server, audit_config):
        """发送邮件产生审计日志"""
        _, server = audit_server
        audit = AuditLogger(server.db)

        token = await register_and_login(client, "audit_sender")
        await client.request(Action.REGISTER, {
            "username": "audit_recv", "password": "TestPass123"
        })

        await client.request(Action.SEND_MAIL, {
            "to": ["audit_recv@alpha.local"],
            "subject": "审计测试",
            "body": "审计日志验证"
        }, token=token)

        logs = await audit.query_logs(action="SEND_MAIL", user_id="audit_sender@alpha.local")
        assert len(logs) >= 1
        detail = json.loads(logs[0]["detail"])
        assert "email_id" in detail
        assert "audit_recv@alpha.local" in detail["to_users"]

    @pytest.mark.asyncio
    async def test_recall_audit_log(self, client, audit_server, audit_config):
        """邮件撤回产生审计日志"""
        _, server = audit_server
        audit = AuditLogger(server.db)

        token = await register_and_login(client, "audit_recall_s")
        await client.request(Action.REGISTER, {
            "username": "audit_recall_r", "password": "TestPass123"
        })

        resp = await client.request(Action.SEND_MAIL, {
            "to": ["audit_recall_r@alpha.local"],
            "subject": "撤回审计", "body": "test"
        }, token=token)
        email_id = resp["payload"]["email_id"]

        sig = compute_hmac(
            audit_config.security.jwt_secret,
            f"RECALL:{email_id}:audit_recall_s@alpha.local"
        )
        await client.request(Action.RECALL_MAIL, {
            "email_id": email_id, "signature": sig
        }, token=token)

        logs = await audit.query_logs(action="RECALL_MAIL", user_id="audit_recall_s@alpha.local")
        assert len(logs) >= 1
        detail = json.loads(logs[0]["detail"])
        assert detail["success"] is True
        assert detail["email_id"] == email_id

    @pytest.mark.asyncio
    async def test_rate_limit_audit_log(self, client, audit_server, audit_config):
        """发送限流触发审计日志"""
        _, server = audit_server
        audit = AuditLogger(server.db)

        token = await register_and_login(client, "audit_rate_user")
        await client.request(Action.REGISTER, {
            "username": "audit_rate_recv", "password": "TestPass123"
        })

        # 发送到达限流阈值
        for i in range(audit_config.security.max_send_per_minute + 1):
            await client.request(Action.SEND_MAIL, {
                "to": ["audit_rate_recv@alpha.local"],
                "subject": f"Rate {i}", "body": "test"
            }, token=token)

        logs = await audit.query_logs(action="RATE_LIMIT")
        assert len(logs) >= 1
        assert logs[0]["level"] == "WARN"
        detail = json.loads(logs[0]["detail"])
        assert detail["triggered_by"] == "SEND_MAIL"


class TestAuditLogFormat:
    """审计日志格式验证"""

    @pytest.mark.asyncio
    async def test_log_format_fields(self, client, audit_server, audit_config):
        """日志包含所有必要字段"""
        _, server = audit_server
        audit = AuditLogger(server.db)

        await client.request(Action.REGISTER, {
            "username": "fmt_user", "password": "TestPass123"
        })

        logs = await audit.query_logs(action="REGISTER", user_id="fmt_user")
        assert len(logs) >= 1
        log = logs[0]

        # 验证必要字段
        assert "log_id" in log and log["log_id"]
        assert "timestamp" in log and log["timestamp"]
        assert "action" in log and log["action"]
        assert "level" in log and log["level"]
        assert "user_id" in log
        # detail 是 JSON 字符串
        assert log["detail"] is not None
        parsed = json.loads(log["detail"])
        assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_log_level_correctness(self, client, audit_server, audit_config):
        """日志级别正确性"""
        _, server = audit_server
        audit = AuditLogger(server.db)

        # INFO 级别：成功注册
        await client.request(Action.REGISTER, {
            "username": "level_user", "password": "TestPass123"
        })
        info_logs = await audit.query_logs(action="REGISTER", level="INFO")
        assert len(info_logs) >= 1

        # WARN 级别：登录失败
        await client.request(Action.LOGIN, {
            "username": "level_user", "password": "WrongPass000"
        })
        warn_logs = await audit.query_logs(action="LOGIN", level="WARN")
        assert len(warn_logs) >= 1
