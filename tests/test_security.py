"""
M6 安全加固测试 - 发送频率限制/钓鱼检测/XSS防护/撤回安全核验
"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.protocol import Action, StatusCode
from shared.crypto import compute_hmac
from server.main import EmailServer
from server.config import ServerConfig
from server.security.spam_detector import SpamDetector, SpamResult
from server.security.sanitizer import HTMLSanitizer
from client.connection import Connection


@pytest.fixture
def sec_config():
    """安全测试服务器配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18060
    config.data_dir = "./data/test_security"
    config.security.jwt_secret = "test-jwt-secret-security"
    config.security.bcrypt_cost = 4
    config.security.recall_window_minutes = 5
    config.security.max_send_per_minute = 5    # 测试用较小值
    config.security.max_send_per_hour = 10
    return config


@pytest.fixture
async def sec_server(sec_config):
    """启动安全测试服务器"""
    db_path = os.path.join(sec_config.data_dir, "safeemail.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    server = EmailServer(sec_config)
    os.makedirs(sec_config.data_dir, exist_ok=True)
    await server._init_services()

    srv = await asyncio.start_server(
        server.handler.handle_connection,
        sec_config.host,
        sec_config.port
    )
    yield srv, server
    srv.close()
    await srv.wait_closed()
    await server.db.close()


@pytest.fixture
async def client(sec_config, sec_server):
    """客户端连接"""
    conn = Connection(sec_config.host, sec_config.port)
    await conn.connect()
    yield conn
    await conn.close()


async def register_and_login(client, username, password, domain="alpha.local"):
    """辅助: 注册并登录，返回 token"""
    await client.request(Action.REGISTER, {
        "username": username, "password": password, "domain": domain
    })
    resp = await client.request(Action.LOGIN, {
        "username": username, "password": password
    })
    return resp.get("payload", {}).get("access_token", "")


# =====================
# TC-021: 高频发送限流
# =====================

@pytest.mark.asyncio
async def test_send_rate_limit_per_minute(client, sec_server, sec_config):
    """TC-021: 1分钟内发送超过限制后被拒绝"""
    token = await register_and_login(client, "rate_user", "TestPass123")

    # 注册一个收件人
    await client.request(Action.REGISTER, {
        "username": "rate_recv", "password": "TestPass123", "domain": "alpha.local"
    })

    # 发送 max_per_minute 封邮件（应该都成功）
    for i in range(sec_config.security.max_send_per_minute):
        resp = await client.request(Action.SEND_MAIL, {
            "to": ["rate_recv@alpha.local"],
            "subject": f"Rate test {i}",
            "body": f"Body {i}"
        }, token=token)
        assert resp["status"] == StatusCode.OK, f"第 {i+1} 封发送失败: {resp.get('message')}"

    # 第 max+1 封应被限流
    resp = await client.request(Action.SEND_MAIL, {
        "to": ["rate_recv@alpha.local"],
        "subject": "Over limit",
        "body": "Should be blocked"
    }, token=token)
    assert resp["status"] == StatusCode.TOO_MANY_REQUESTS


# =====================
# TC-022: 钓鱼邮件识别
# =====================

@pytest.mark.asyncio
async def test_spam_detector_phishing_url():
    """TC-022a: 包含黑名单 URL 的邮件被标记"""
    detector = SpamDetector()
    result = detector.detect(
        subject="Important Notice",
        body="请点击 https://evil.com/verify 验证您的账号",
        from_user="attacker@evil.com"
    )
    assert result.is_spam is True
    assert result.spam_score >= 5.0
    assert len(result.flagged_urls) > 0
    assert "evil.com" in result.flagged_urls[0]


@pytest.mark.asyncio
async def test_spam_detector_sensitive_keywords():
    """TC-022b: 包含大量敏感关键词的邮件被标记"""
    detector = SpamDetector()
    result = detector.detect(
        subject="恭喜您中奖了！",
        body="紧急转账到我们的银行卡，免费领取奖品！点击链接领取",
        from_user="scammer@test.com"
    )
    assert result.is_spam is True
    assert result.spam_score >= 5.0
    assert len(result.reasons) > 0


@pytest.mark.asyncio
async def test_spam_detector_clean_email():
    """TC-022c: 正常邮件不被标记"""
    detector = SpamDetector()
    result = detector.detect(
        subject="会议通知",
        body="明天上午 10 点在 A 会议室开会，请准时参加。",
        from_user="alice@company.com"
    )
    assert result.is_spam is False
    assert result.spam_score < 5.0


@pytest.mark.asyncio
async def test_spam_detector_homograph():
    """TC-022d: Homograph 攻击检测"""
    detector = SpamDetector()
    # 使用 Cyrillic 'а' (U+0430) 替代 Latin 'a'
    result = detector.detect(
        subject="Account Alert",
        body="Your \u0430ccount h\u0430s been compromised, \u0430ct now!",
        from_user="alert@test.com"
    )
    assert result.is_spam is True
    assert any("Homograph" in r for r in result.reasons)


@pytest.mark.asyncio
async def test_phishing_mail_flagged_in_server(client, sec_server, sec_config):
    """TC-022e: 通过服务器发送钓鱼邮件，返回 spam_warning"""
    token = await register_and_login(client, "phish_sender", "TestPass123")
    await client.request(Action.REGISTER, {
        "username": "phish_recv", "password": "TestPass123", "domain": "alpha.local"
    })

    resp = await client.request(Action.SEND_MAIL, {
        "to": ["phish_recv@alpha.local"],
        "subject": "恭喜您中奖通知",
        "body": "点击 https://evil.com/claim 领取奖品，紧急转账到银行卡"
    }, token=token)
    assert resp["status"] == StatusCode.OK
    assert resp["payload"].get("spam_warning") is True


# =====================
# TC-023: XSS 注入防护
# =====================

@pytest.mark.asyncio
async def test_xss_script_removal():
    """TC-023a: <script> 标签被移除"""
    sanitizer = HTMLSanitizer()
    html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
    result = sanitizer.sanitize(html)
    assert "<script>" not in result
    assert "alert" not in result
    assert "<p>" in result


@pytest.mark.asyncio
async def test_xss_event_attributes_removal():
    """TC-023b: 事件属性被移除"""
    sanitizer = HTMLSanitizer()
    html = '<img src="x" onerror="fetch(\'/steal\')">'
    result = sanitizer.sanitize(html)
    assert "onerror" not in result
    assert "fetch" not in result


@pytest.mark.asyncio
async def test_xss_iframe_removal():
    """TC-023c: <iframe> 标签被移除"""
    sanitizer = HTMLSanitizer()
    html = '<p>Content</p><iframe src="https://evil.com"></iframe><p>More</p>'
    result = sanitizer.sanitize(html)
    assert "<iframe" not in result
    assert "evil.com" not in result
    assert "<p>" in result


@pytest.mark.asyncio
async def test_xss_safe_tags_preserved():
    """TC-023d: 安全标签被保留"""
    sanitizer = HTMLSanitizer()
    html = '<p>Hello <b>World</b> <a href="https://safe.com">link</a></p>'
    result = sanitizer.sanitize(html)
    assert "<p>" in result
    assert "<b>" in result
    assert "<a " in result
    assert 'href="https://safe.com"' in result


@pytest.mark.asyncio
async def test_xss_javascript_href_removal():
    """TC-023e: javascript: 协议的链接被移除"""
    sanitizer = HTMLSanitizer()
    html = '<a href="javascript:alert(1)">Click</a>'
    result = sanitizer.sanitize(html)
    assert "javascript:" not in result


@pytest.mark.asyncio
async def test_xss_sanitize_in_send_mail(client, sec_server, sec_config):
    """TC-023f: 通过服务器发送含 XSS 的邮件，正文被清洗"""
    token = await register_and_login(client, "xss_sender", "TestPass123")
    await client.request(Action.REGISTER, {
        "username": "xss_recv", "password": "TestPass123", "domain": "alpha.local"
    })

    xss_body = '<p>Hello</p><script>alert("xss")</script><img src="x" onerror="steal()">'
    resp = await client.request(Action.SEND_MAIL, {
        "to": ["xss_recv@alpha.local"],
        "subject": "XSS Test",
        "body": xss_body
    }, token=token)
    assert resp["status"] == StatusCode.OK
    email_id = resp["payload"]["email_id"]

    # 登录收件人读取邮件
    resp2 = await client.request(Action.LOGIN, {
        "username": "xss_recv", "password": "TestPass123"
    })
    token2 = resp2["payload"]["access_token"]

    resp3 = await client.request(Action.READ_MAIL, {"email_id": email_id}, token=token2)
    assert resp3["status"] == StatusCode.OK
    body = resp3["payload"]["body"]
    assert "<script>" not in body
    assert "onerror" not in body
    assert "<p>" in body


# =====================
# TC-024: 伪造撤回拒绝
# =====================

@pytest.mark.asyncio
async def test_recall_forged_by_other_user(client, sec_server, sec_config):
    """TC-024a: 用 B 的 Token 尝试撤回 A 发送的邮件，被拒绝"""
    # 注册两个用户
    token_a = await register_and_login(client, "recall_a", "TestPass123")
    token_b = await register_and_login(client, "recall_b", "TestPass123")

    # A 发送邮件
    resp = await client.request(Action.SEND_MAIL, {
        "to": ["recall_b@alpha.local"],
        "subject": "Recall Test",
        "body": "Test body"
    }, token=token_a)
    assert resp["status"] == StatusCode.OK
    email_id = resp["payload"]["email_id"]

    # B 尝试伪造撤回 A 的邮件
    fake_sig = compute_hmac(
        sec_config.security.jwt_secret,
        f"RECALL:{email_id}:recall_b@alpha.local"
    )
    resp = await client.request(Action.RECALL_MAIL, {
        "email_id": email_id,
        "signature": fake_sig
    }, token=token_b)
    assert resp["status"] == StatusCode.FORBIDDEN
    assert "发件人" in resp.get("message", "")


@pytest.mark.asyncio
async def test_recall_forged_signature(client, sec_server, sec_config):
    """TC-024b: 使用伪造签名撤回邮件，被拒绝"""
    token_a = await register_and_login(client, "recall_sig_a", "TestPass123")
    await client.request(Action.REGISTER, {
        "username": "recall_sig_b", "password": "TestPass123", "domain": "alpha.local"
    })

    # 发送邮件
    resp = await client.request(Action.SEND_MAIL, {
        "to": ["recall_sig_b@alpha.local"],
        "subject": "Sig Test",
        "body": "Test body"
    }, token=token_a)
    email_id = resp["payload"]["email_id"]

    # 使用错误密钥生成签名
    fake_sig = compute_hmac(
        "wrong-secret-key",
        f"RECALL:{email_id}:recall_sig_a@alpha.local"
    )
    resp = await client.request(Action.RECALL_MAIL, {
        "email_id": email_id,
        "signature": fake_sig
    }, token=token_a)
    assert resp["status"] == StatusCode.FORBIDDEN
    assert "签名" in resp.get("message", "")
