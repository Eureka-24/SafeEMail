"""
M8 快捷操作与快速回复测试
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
from server.mail.quick_reply import QuickReplyGenerator, REPLY_TEMPLATES, KEYWORD_REPLIES
from server.intelligence.action_engine import (
    ActionEngine, ACTION_SCHEDULE, ACTION_CONFIRM, ACTION_REJECT,
    ACTION_SAFE_LINK, ACTION_SUMMARY
)
from client.connection import Connection


@pytest.fixture
def qa_config():
    """M8 测试服务器配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18080
    config.data_dir = "./data/test_quick_action"
    config.security.jwt_secret = "test-jwt-secret-qa"
    config.security.bcrypt_cost = 4
    config.security.max_send_per_minute = 50
    config.security.max_send_per_hour = 200
    return config


@pytest.fixture
async def qa_server(qa_config):
    """启动测试服务器"""
    db_path = os.path.join(qa_config.data_dir, "safeemail.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    server = EmailServer(qa_config)
    os.makedirs(qa_config.data_dir, exist_ok=True)
    await server._init_services()

    srv = await asyncio.start_server(
        server.handler.handle_connection,
        qa_config.host,
        qa_config.port
    )
    yield srv, server
    srv.close()
    await srv.wait_closed()
    await server.db.close()


@pytest.fixture
async def client(qa_config, qa_server):
    """客户端连接"""
    conn = Connection(qa_config.host, qa_config.port)
    await conn.connect()
    yield conn
    await conn.close()


async def register_and_login(client, username, password="TestPass123"):
    """辅助：注册并登录，返回 token"""
    await client.request(Action.REGISTER, {
        "username": username, "password": password
    })
    resp = await client.request(Action.LOGIN, {
        "username": username, "password": password
    })
    return resp["payload"]["access_token"]


# =====================
# 快速回复单元测试
# =====================

class TestQuickReplyGenerator:
    """快速回复建议生成器单元测试"""

    @pytest.mark.asyncio
    async def test_generate_basic_replies(self):
        """基本回复建议生成"""
        gen = QuickReplyGenerator()
        replies = gen.generate_replies(
            email={"subject": "项目进度汇报", "body": "请查看本周工作进展", "from_user": "alice@test.com"},
            category="工作"
        )
        assert len(replies) == 3
        for r in replies:
            assert "text" in r
            assert "auto_to" in r
            assert "auto_subject" in r
            assert r["auto_to"] == "alice@test.com"
            assert r["auto_subject"] == "Re: 项目进度汇报"

    @pytest.mark.asyncio
    async def test_keyword_triggered_reply(self):
        """关键词触发特定回复"""
        gen = QuickReplyGenerator()
        replies = gen.generate_replies(
            email={"subject": "会议通知", "body": "明天下午2点开技术评审会议", "from_user": "bob@test.com"},
            category="工作"
        )
        assert len(replies) == 3
        texts = [r["text"] for r in replies]
        # 应包含会议相关的关键词回复
        assert any("会议" in t or "参加" in t or "准时" in t for t in texts)

    @pytest.mark.asyncio
    async def test_question_detection_reply(self):
        """问句检测生成针对性回复"""
        gen = QuickReplyGenerator()
        replies = gen.generate_replies(
            email={"subject": "请求", "body": "能否帮忙审阅一下这份文档？", "from_user": "carol@test.com"},
            category="工作"
        )
        texts = [r["text"] for r in replies]
        # 应包含对问句的回复
        assert any("可以" in t or "没问题" in t or "好的" in t for t in texts)

    @pytest.mark.asyncio
    async def test_social_category_replies(self):
        """社交类邮件回复"""
        gen = QuickReplyGenerator()
        replies = gen.generate_replies(
            email={"subject": "生日快乐", "body": "祝你生日快乐！", "from_user": "dave@test.com"},
            category="社交"
        )
        assert len(replies) == 3
        texts = [r["text"] for r in replies]
        assert any("生日" in t or "祝" in t or "快乐" in t for t in texts)

    @pytest.mark.asyncio
    async def test_auto_subject_no_double_re(self):
        """Re: 前缀不会重复"""
        gen = QuickReplyGenerator()
        replies = gen.generate_replies(
            email={"subject": "Re: 原始主题", "body": "好的", "from_user": "e@test.com"},
            category="其他"
        )
        assert replies[0]["auto_subject"] == "Re: 原始主题"

    @pytest.mark.asyncio
    async def test_empty_email(self):
        """空邮件也能生成回复"""
        gen = QuickReplyGenerator()
        replies = gen.generate_replies(
            email={"subject": "", "body": "", "from_user": "f@test.com"},
            category=None
        )
        assert len(replies) == 3


# =====================
# 快捷操作引擎单元测试
# =====================

class TestActionEngine:
    """快捷操作引擎单元测试"""

    @pytest.mark.asyncio
    async def test_build_schedule_action(self):
        """检测日程并生成操作"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("明天下午3点开技术评审会议", "email-001")
        types = [a["type"] for a in actions]
        assert ACTION_SCHEDULE in types
        schedule = next(a for a in actions if a["type"] == ACTION_SCHEDULE)
        assert "time" in schedule["data"]
        assert "event" in schedule["data"]
        assert "signature" in schedule

    @pytest.mark.asyncio
    async def test_build_confirm_reject_actions(self):
        """检测确认/拒绝场景"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("请确认是否同意本次方案", "email-002")
        types = [a["type"] for a in actions]
        assert ACTION_CONFIRM in types
        assert ACTION_REJECT in types

    @pytest.mark.asyncio
    async def test_build_safe_link_action(self):
        """检测URL生成安全链接操作"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("请访问 https://example.com/doc 查看文档", "email-003")
        types = [a["type"] for a in actions]
        assert ACTION_SAFE_LINK in types
        link_action = next(a for a in actions if a["type"] == ACTION_SAFE_LINK)
        assert link_action["data"]["safe"] is True

    @pytest.mark.asyncio
    async def test_build_dangerous_link(self):
        """检测危险链接"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("点击 https://bit.ly/abc123 领取奖励", "email-004")
        link_actions = [a for a in actions if a["type"] == ACTION_SAFE_LINK]
        assert len(link_actions) > 0
        assert link_actions[0]["data"]["safe"] is False

    @pytest.mark.asyncio
    async def test_build_summary_action(self):
        """始终生成摘要操作"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("这是一封普通的邮件正文内容", "email-005")
        types = [a["type"] for a in actions]
        assert ACTION_SUMMARY in types

    @pytest.mark.asyncio
    async def test_execute_schedule(self):
        """执行日程添加操作"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("明天下午3点开评审会议", "email-006")
        schedule = next(a for a in actions if a["type"] == ACTION_SCHEDULE)
        success, msg, result = engine.execute_action("email-006", schedule)
        assert success
        assert "已添加日程" in msg
        assert "event" in result

    @pytest.mark.asyncio
    async def test_execute_confirm_needs_confirmation(self):
        """确认操作需要二次确认"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("请确认是否参加培训", "email-007")
        confirm_action = next(a for a in actions if a["type"] == ACTION_CONFIRM)

        # 未二次确认 → 拒绝
        success, msg, result = engine.execute_action("email-007", confirm_action, confirm=False)
        assert not success
        assert result.get("need_confirm") is True

        # 二次确认 → 成功
        success, msg, result = engine.execute_action("email-007", confirm_action, confirm=True)
        assert success
        assert "已确认" in msg

    @pytest.mark.asyncio
    async def test_execute_reject(self):
        """执行拒绝操作"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("请确认是否参加培训", "email-008")
        reject_action = next(a for a in actions if a["type"] == ACTION_REJECT)
        success, msg, result = engine.execute_action("email-008", reject_action, confirm=True)
        assert success
        assert "已拒绝" in msg

    @pytest.mark.asyncio
    async def test_execute_safe_link(self):
        """执行安全链接跳转"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("文档在 https://docs.example.com/api", "email-009")
        link_action = next(a for a in actions if a["type"] == ACTION_SAFE_LINK)
        success, msg, result = engine.execute_action("email-009", link_action)
        assert success
        assert result["safe"] is True

    @pytest.mark.asyncio
    async def test_execute_blocked_link(self):
        """阻止危险链接"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("中奖 https://phishing-site.com/win", "email-010")
        link_action = next(a for a in actions if a["type"] == ACTION_SAFE_LINK)
        success, msg, result = engine.execute_action("email-010", link_action)
        assert not success
        assert result["blocked"] is True

    @pytest.mark.asyncio
    async def test_execute_summary(self):
        """执行摘要提取"""
        engine = ActionEngine(hmac_secret="test-secret")
        actions = engine.build_actions("这是一段需要提取摘要的邮件正文内容", "email-011")
        summary_action = next(a for a in actions if a["type"] == ACTION_SUMMARY)
        success, msg, result = engine.execute_action("email-011", summary_action)
        assert success
        assert len(result["summary"]) > 0

    @pytest.mark.asyncio
    async def test_signature_verification_fail(self):
        """签名伪造检测"""
        engine = ActionEngine(hmac_secret="test-secret")
        fake_action = {
            "type": ACTION_SUMMARY,
            "label": "📋 复制摘要",
            "data": {"summary": "伪造的摘要"},
            "signature": "fake-signature-123"
        }
        success, msg, result = engine.execute_action("email-012", fake_action)
        assert not success
        assert "签名验证失败" in msg

    @pytest.mark.asyncio
    async def test_invalid_action_type(self):
        """无效操作类型"""
        engine = ActionEngine(hmac_secret="test-secret")
        bad_action = {"type": "hacker_action", "data": {}, "signature": "x"}
        success, msg, result = engine.execute_action("email-013", bad_action)
        assert not success
        assert "不支持" in msg


# =====================
# 端到端集成测试
# =====================

class TestQuickReplyIntegration:
    """快速回复集成测试"""

    @pytest.mark.asyncio
    async def test_quick_reply_for_received_email(self, client, qa_server, qa_config):
        """收到邮件后获取快速回复建议"""
        _, server = qa_server
        # 注册两个用户
        token_sender = await register_and_login(client, "qa_sender1")
        await client.request(Action.REGISTER, {"username": "qa_recv1", "password": "TestPass123"})

        # 发送邮件
        resp = await client.request(Action.SEND_MAIL, {
            "to": ["qa_recv1@alpha.local"],
            "subject": "会议通知",
            "body": "明天下午2点开项目评审会议，请准时参加"
        }, token=token_sender)
        assert resp["status"] == StatusCode.OK
        email_id = resp["payload"]["email_id"]

        # 用收件人身份获取快速回复
        resp_login = await client.request(Action.LOGIN, {
            "username": "qa_recv1", "password": "TestPass123"
        })
        token_recv = resp_login["payload"]["access_token"]

        resp = await client.request(Action.QUICK_REPLY, {
            "email_id": email_id
        }, token=token_recv)
        assert resp["status"] == StatusCode.OK
        suggestions = resp["payload"]["suggestions"]
        assert len(suggestions) > 0
        assert all("text" in s and "auto_to" in s and "auto_subject" in s for s in suggestions)
        assert suggestions[0]["auto_to"] == "qa_sender1@alpha.local"

    @pytest.mark.asyncio
    async def test_quick_reply_nonexistent_email(self, client, qa_server, qa_config):
        """不存在的邮件返回 NOT_FOUND"""
        token = await register_and_login(client, "qa_user2")
        resp = await client.request(Action.QUICK_REPLY, {
            "email_id": "nonexistent-id"
        }, token=token)
        assert resp["status"] == StatusCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_quick_reply_missing_email_id(self, client, qa_server, qa_config):
        """缺少 email_id 返回 BAD_REQUEST"""
        token = await register_and_login(client, "qa_user3")
        resp = await client.request(Action.QUICK_REPLY, {}, token=token)
        assert resp["status"] == StatusCode.BAD_REQUEST


class TestExecActionIntegration:
    """快捷操作集成测试"""

    @pytest.mark.asyncio
    async def test_exec_action_with_schedule(self, client, qa_server, qa_config):
        """执行日程操作端到端"""
        _, server = qa_server
        token_sender = await register_and_login(client, "qa_act_sender")
        await client.request(Action.REGISTER, {"username": "qa_act_recv", "password": "TestPass123"})

        # 发送含日程的邮件
        resp = await client.request(Action.SEND_MAIL, {
            "to": ["qa_act_recv@alpha.local"],
            "subject": "培训通知",
            "body": "请确认是否参加明天下午3点的技术培训分享"
        }, token=token_sender)
        assert resp["status"] == StatusCode.OK
        email_id = resp["payload"]["email_id"]

        # 验证 actions 已存储
        email = await server.db.fetchone(
            "SELECT actions FROM emails WHERE email_id = ?", (email_id,)
        )
        assert email["actions"] is not None
        actions = json.loads(email["actions"])
        assert len(actions) > 0

        # 收件人执行操作
        resp_login = await client.request(Action.LOGIN, {
            "username": "qa_act_recv", "password": "TestPass123"
        })
        token_recv = resp_login["payload"]["access_token"]

        # 找到日程操作的索引
        schedule_idx = next((i for i, a in enumerate(actions) if a["type"] == "schedule"), None)
        if schedule_idx is not None:
            resp = await client.request(Action.EXEC_ACTION, {
                "email_id": email_id,
                "action_index": schedule_idx
            }, token=token_recv)
            assert resp["status"] == StatusCode.OK
            assert "已添加日程" in resp["message"]

    @pytest.mark.asyncio
    async def test_exec_confirm_needs_double_confirm(self, client, qa_server, qa_config):
        """确认操作需要二次确认"""
        _, server = qa_server
        token_sender = await register_and_login(client, "qa_cfm_sender")
        await client.request(Action.REGISTER, {"username": "qa_cfm_recv", "password": "TestPass123"})

        resp = await client.request(Action.SEND_MAIL, {
            "to": ["qa_cfm_recv@alpha.local"],
            "subject": "审批请求",
            "body": "请确认是否同意本次方案调整"
        }, token=token_sender)
        email_id = resp["payload"]["email_id"]

        email = await server.db.fetchone(
            "SELECT actions FROM emails WHERE email_id = ?", (email_id,)
        )
        actions = json.loads(email["actions"])
        confirm_idx = next(i for i, a in enumerate(actions) if a["type"] == "confirm")

        resp_login = await client.request(Action.LOGIN, {
            "username": "qa_cfm_recv", "password": "TestPass123"
        })
        token_recv = resp_login["payload"]["access_token"]

        # 第一次不带 confirm → 提示需要确认
        resp = await client.request(Action.EXEC_ACTION, {
            "email_id": email_id,
            "action_index": confirm_idx,
            "confirm": False
        }, token=token_recv)
        assert resp["status"] == StatusCode.BAD_REQUEST
        assert resp["payload"].get("need_confirm") is True

        # 第二次带 confirm → 成功
        resp = await client.request(Action.EXEC_ACTION, {
            "email_id": email_id,
            "action_index": confirm_idx,
            "confirm": True
        }, token=token_recv)
        assert resp["status"] == StatusCode.OK
        assert "已确认" in resp["message"]

    @pytest.mark.asyncio
    async def test_exec_action_missing_params(self, client, qa_server, qa_config):
        """缺少参数返回 BAD_REQUEST"""
        token = await register_and_login(client, "qa_miss_user")
        resp = await client.request(Action.EXEC_ACTION, {
            "email_id": "some-id"
        }, token=token)
        assert resp["status"] == StatusCode.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_exec_action_invalid_index(self, client, qa_server, qa_config):
        """无效 action_index"""
        _, server = qa_server
        token_sender = await register_and_login(client, "qa_idx_sender")
        await client.request(Action.REGISTER, {"username": "qa_idx_recv", "password": "TestPass123"})

        resp = await client.request(Action.SEND_MAIL, {
            "to": ["qa_idx_recv@alpha.local"],
            "subject": "测试",
            "body": "这是一封测试邮件正文内容"
        }, token=token_sender)
        email_id = resp["payload"]["email_id"]

        resp_login = await client.request(Action.LOGIN, {
            "username": "qa_idx_recv", "password": "TestPass123"
        })
        token_recv = resp_login["payload"]["access_token"]

        resp = await client.request(Action.EXEC_ACTION, {
            "email_id": email_id,
            "action_index": 999
        }, token=token_recv)
        assert resp["status"] == StatusCode.BAD_REQUEST
