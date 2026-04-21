# 智能安全邮箱系统 — 技术规格说明书（SPEC）

| 字段     | 内容                       |
| -------- | -------------------------- |
| 产品名称 | SafeEmail 智能安全邮箱系统 |
| 文档版本 | v1.0                       |
| 创建日期 | 2026-04-21                 |
| 关联文档 | docs/PRD.md                |

---

## 1 技术选型

| 层面       | 选型                         | 说明                                    |
| ---------- | ---------------------------- | --------------------------------------- |
| 编程语言   | Python 3.10+                 | asyncio 原生支持，生态丰富               |
| 网络框架   | asyncio + 原生 TCP Socket    | 自定义协议，异步非阻塞                   |
| 数据存储   | SQLite（WAL 模式）           | 轻量本地部署，事务保证一致性             |
| 加密       | cryptography + PyJWT + bcrypt| TLS/JWT/密码哈希/HMAC                   |
| 搜索       | 自建倒排索引                  | 满足禁止使用成熟开源系统约束             |
| 中文分词   | jieba                        | TF-IDF 关键词提取                       |
| 测试       | pytest + pytest-asyncio      | 异步测试支持                             |
| TLS 证书   | 自签名证书（开发环境）        | 使用 cryptography 库生成                 |

---

## 2 项目结构

```
SafeEmail/
├── server/                      # 服务端
│   ├── __init__.py
│   ├── main.py                  # 服务器启动入口
│   ├── config.py                # 配置管理
│   ├── protocol/                # 协议层
│   │   ├── __init__.py
│   │   ├── handler.py           # 消息路由与分发
│   │   ├── codec.py             # JSON 编解码（\r\n 分隔）
│   │   └── actions.py           # Action 枚举定义
│   ├── auth/                    # 认证模块
│   │   ├── __init__.py
│   │   ├── service.py           # 注册/登录/登出/Token 管理
│   │   ├── jwt_util.py          # JWT 签发与验证
│   │   ├── password.py          # bcrypt 密码哈希
│   │   └── rate_limiter.py      # 暴力破解防护/速率限制
│   ├── mail/                    # 邮件模块
│   │   ├── __init__.py
│   │   ├── service.py           # 邮件收发/撤回/草稿/群发
│   │   ├── relay.py             # S2S 跨域中继
│   │   ├── group.py             # 群组管理
│   │   └── quick_reply.py       # 快捷回复建议
│   ├── storage/                 # 存储引擎
│   │   ├── __init__.py
│   │   ├── database.py          # SQLite 数据库管理
│   │   ├── models.py            # 数据模型（ORM）
│   │   ├── attachment.py        # 附件存储与去重
│   │   └── migrations.py        # 数据库初始化/迁移
│   ├── security/                # 安全防护
│   │   ├── __init__.py
│   │   ├── tls.py               # TLS 配置
│   │   ├── sanitizer.py         # HTML 清洗/XSS 防护
│   │   ├── spam_detector.py     # 钓鱼/垃圾邮件检测
│   │   └── rate_limit.py        # 发送频率/连接限流
│   ├── intelligence/            # 智能引擎
│   │   ├── __init__.py
│   │   ├── classifier.py        # 邮件分类（朴素贝叶斯）
│   │   ├── keyword_extractor.py # TF-IDF 关键词提取
│   │   ├── search_engine.py     # 倒排索引 + 模糊搜索
│   │   └── action_engine.py     # 快捷操作引擎
│   └── audit/                   # 审计日志
│       ├── __init__.py
│       └── logger.py            # 审计日志记录
├── client/                      # 客户端
│   ├── __init__.py
│   ├── main.py                  # 客户端启动入口（CLI/TUI）
│   ├── connection.py            # TCP 连接管理（TLS）
│   ├── session.py               # 会话/Token 管理
│   ├── commands/                # 用户命令处理
│   │   ├── __init__.py
│   │   ├── auth.py              # 注册/登录/登出
│   │   ├── mail.py              # 邮件操作
│   │   ├── attachment.py        # 附件操作
│   │   └── group.py             # 群组操作
│   └── ui/                      # 界面层
│       ├── __init__.py
│       └── console.py           # 控制台交互界面
├── shared/                      # 公共模块
│   ├── __init__.py
│   ├── protocol.py              # 协议常量与工具函数
│   └── crypto.py                # 公共加密工具
├── tests/                       # 测试
│   ├── __init__.py
│   ├── test_auth.py             # 认证测试
│   ├── test_mail.py             # 邮件功能测试
│   ├── test_relay.py            # 跨域中继测试
│   ├── test_attachment.py       # 附件/去重测试
│   ├── test_security.py         # 安全测试
│   ├── test_intelligence.py     # 智能功能测试
│   └── test_concurrent.py       # 并发/压力测试
├── scripts/                     # 启动脚本
│   ├── start_servers.py         # 一键启动双域名服务器
│   ├── generate_certs.py        # 生成自签名 TLS 证书
│   └── seed_data.py             # 填充测试数据
├── config/                      # 配置文件
│   ├── alpha.yaml               # alpha.local 服务器配置
│   └── beta.yaml                # beta.local 服务器配置
├── data/                        # 运行时数据目录（gitignore）
├── certs/                       # TLS 证书目录（gitignore）
├── requirements.txt             # Python 依赖
└── docs/
    ├── PRD.md
    └── SPEC.md
```

---

## 3 通信协议详细设计

### 3.1 传输层

- **传输协议**: TCP + TLS 1.3
- **消息边界**: 每条 JSON 消息以 `\r\n` 作为分隔符
- **编码**: UTF-8
- **最大消息大小**: 15MB（含附件 Base64 编码）

### 3.2 消息结构

```python
# 请求
{
    "version": "1.0",
    "type": "REQUEST",
    "action": "<ACTION_NAME>",
    "request_id": "<uuid4>",
    "token": "<jwt|null>",
    "payload": { ... }
}

# 响应
{
    "version": "1.0",
    "type": "RESPONSE",
    "request_id": "<uuid4>",
    "status": <int>,           # HTTP 风格状态码
    "message": "<描述>",
    "payload": { ... }
}
```

### 3.3 状态码定义

| 状态码 | 含义             |
| ------ | ---------------- |
| 200    | 成功             |
| 201    | 创建成功         |
| 400    | 请求格式错误     |
| 401    | 未认证/Token无效 |
| 403    | 权限不足         |
| 404    | 资源不存在       |
| 409    | 冲突（如重复注册）|
| 429    | 请求过于频繁     |
| 500    | 服务器内部错误   |

### 3.4 S2S 中继协议

服务器间通信采用独立 TLS 连接，使用相同 JSON 协议格式：

```python
# S2S 投递请求
{
    "version": "1.0",
    "type": "S2S_REQUEST",
    "action": "S2S_DELIVER",
    "server_id": "alpha.local",
    "signature": "<HMAC-SHA256 签名>",
    "payload": {
        "email": { ... }  # 完整邮件对象
    }
}
```

- 双向 TLS 认证（mTLS）
- 服务器间共享密钥用于 HMAC 签名验证

---

## 4 数据库设计

### 4.1 数据库选型与配置

- SQLite 3，WAL 模式启用并发读
- 每个域名实例独立数据库文件：`data/{domain}/safeemail.db`

### 4.2 表结构 SQL

```sql
-- 用户表
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,          -- UUID
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,        -- bcrypt hash
    domain TEXT NOT NULL,
    created_at TEXT NOT NULL,           -- ISO8601
    status TEXT NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE|LOCKED
    failed_attempts INTEGER DEFAULT 0,
    locked_until TEXT                   -- ISO8601, nullable
);

-- 邮件表
CREATE TABLE emails (
    email_id TEXT PRIMARY KEY,          -- UUID
    from_user TEXT NOT NULL,            -- user@domain
    to_users TEXT NOT NULL,             -- JSON array
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'DRAFT', -- SENT|DRAFT|RECALLED
    category TEXT,                      -- 智能分类标签
    keywords TEXT,                      -- JSON array
    actions TEXT,                       -- JSON, 快捷操作定义
    created_at TEXT NOT NULL,
    sent_at TEXT,
    is_read INTEGER DEFAULT 0,
    is_spam INTEGER DEFAULT 0,
    spam_score REAL DEFAULT 0.0
);

-- 邮件-收件人关系表（用于收件箱查询）
CREATE TABLE email_recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL,
    recipient TEXT NOT NULL,            -- user@domain
    is_read INTEGER DEFAULT 0,
    is_recalled INTEGER DEFAULT 0,
    FOREIGN KEY (email_id) REFERENCES emails(email_id)
);

-- 附件表
CREATE TABLE attachments (
    attachment_id TEXT PRIMARY KEY,
    email_id TEXT NOT NULL,
    file_hash TEXT NOT NULL,            -- SHA-256
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    ref_count INTEGER DEFAULT 1,
    hmac_value TEXT NOT NULL,           -- 完整性校验
    FOREIGN KEY (email_id) REFERENCES emails(email_id)
);

-- 群组表
CREATE TABLE groups (
    group_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    group_name TEXT NOT NULL,
    members TEXT NOT NULL,              -- JSON array
    FOREIGN KEY (owner_id) REFERENCES users(user_id)
);

-- 审计日志表
CREATE TABLE audit_logs (
    log_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    user_id TEXT,
    action TEXT NOT NULL,
    ip_address TEXT,
    detail TEXT,                        -- JSON
    level TEXT NOT NULL DEFAULT 'INFO'  -- INFO|WARN|ERROR
);

-- Token 黑名单表
CREATE TABLE token_blacklist (
    jti TEXT PRIMARY KEY,
    expired_at TEXT NOT NULL
);

-- 倒排索引表
CREATE TABLE search_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    email_id TEXT NOT NULL,
    field TEXT NOT NULL,                -- subject|body|from|to
    score REAL DEFAULT 1.0,
    FOREIGN KEY (email_id) REFERENCES emails(email_id)
);
CREATE INDEX idx_search_keyword ON search_index(keyword);

-- IP 限流记录表
CREATE TABLE ip_rate_limits (
    ip_address TEXT NOT NULL,
    attempt_time TEXT NOT NULL,
    action_type TEXT NOT NULL           -- LOGIN|SEND|CONNECT
);
CREATE INDEX idx_ip_rate ON ip_rate_limits(ip_address, action_type);
```

---

## 5 核心模块详细设计

### 5.1 认证模块

#### JWT Token 结构

```python
# Access Token Payload
{
    "sub": "<user_id>",
    "username": "<username>",
    "domain": "<domain>",
    "jti": "<uuid4>",           # 唯一标识，用于黑名单
    "iat": <timestamp>,
    "exp": <timestamp>,         # iat + 30min
    "type": "access"
}

# Refresh Token Payload
{
    "sub": "<user_id>",
    "jti": "<uuid4>",
    "iat": <timestamp>,
    "exp": <timestamp>,         # iat + 7days
    "type": "refresh"
}
```

#### 密码策略

- 长度 ≥ 8 位
- 必须包含：大写字母 + 小写字母 + 数字
- 存储：bcrypt, cost=12

#### 防暴力破解

```
同一 IP:
  - 5 次失败/5min → 锁定 IP 15min
  - 3 次失败后 → 触发 CAPTCHA（简单数学题验证码）

同一账号:
  - 10 次失败/10min → 锁定账号 30min
```

### 5.2 邮件收发流程

```
发送邮件流程:
1. 客户端发送 SEND_MAIL 请求
2. 服务端验证 Token
3. 检查发送频率限制（10封/min, 60封/hour）
4. 解析收件人列表
5. 对邮件正文执行 HTML Sanitize
6. 智能引擎：提取关键词、分类、钓鱼检测
7. 处理附件（计算哈希、去重存储）
8. 分拣：
   a. 本域收件人 → 直接写入本地数据库
   b. 跨域收件人 → 通过 S2S Relay 投递
9. 写入发件箱记录
10. 更新搜索索引
11. 记录审计日志
12. 返回成功响应
```

### 5.3 邮件撤回流程

```
撤回校验链:
1. 验证请求者身份（Token.sub == email.from_user）
2. 验证 HMAC 签名（防伪造）
3. 检查时间窗口（sent_at + 5min > now）
4. 检查幂等性（status != RECALLED）
5. 执行撤回：
   a. 本域：更新 email_recipients.is_recalled = 1
   b. 跨域：发送 S2S_RECALL 请求到目标服务器
6. 更新邮件状态为 RECALLED
7. 若邮件已读，返回提示"收件人可能已阅"
```

### 5.4 附件去重机制

```
上传流程:
1. 接收附件 Base64 数据，解码
2. 计算 SHA-256 哈希
3. 查询数据库是否存在相同哈希
   a. 存在 → ref_count + 1，复用 storage_path
   b. 不存在 → 写入文件，计算 HMAC，创建新记录
4. 存储路径: attachments/{hash[0:2]}/{hash[2:4]}/{full_hash}

删除流程:
1. ref_count - 1
2. 若 ref_count == 0 → 物理删除文件

完整性校验:
- 读取附件时重新计算 HMAC 与存储值比对
- 不匹配则拒绝返回并记录告警
```

### 5.5 智能引擎

#### 关键词提取（TF-IDF）

- 中文：jieba 分词 → 去停用词 → TF-IDF 计算 → Top-5
- 英文：空格分词 → 去停用词 → TF-IDF 计算 → Top-5

#### 邮件分类（朴素贝叶斯）

- 预定义类别：`工作`、`通知`、`广告/营销`、`社交`、`其他`
- 特征：TF-IDF 关键词向量
- 训练数据：内置小规模种子数据集，支持用户修正反馈

#### 模糊搜索

- 倒排索引：写入时构建，字段包含 subject/body/from/to
- 模糊匹配：编辑距离 ≤ 2 的容错
- N-Gram (N=3) 索引加速
- 结果按相关性评分排序

### 5.6 安全防护

#### 钓鱼检测

```python
检测流程:
1. 提取正文中所有 URL
2. 域名黑名单匹配（内置列表）
3. Homograph 攻击检测（Unicode 相似字符）
4. 敏感关键词评分（"中奖"/"紧急转账"/"验证码"等）
5. 发件人信誉评分查询
6. 综合评分 > 阈值 → 标记为垃圾邮件
```

#### HTML 清洗

- 移除标签：`<script>`, `<iframe>`, `<object>`, `<embed>`
- 移除属性：`onerror`, `onclick`, `onload` 等所有事件属性
- 保留安全标签：`<p>`, `<br>`, `<b>`, `<i>`, `<a>`（仅保留 href）

---

## 6 配置文件设计

```yaml
# config/alpha.yaml
server:
  domain: "alpha.local"
  host: "127.0.0.1"
  port: 8001
  data_dir: "./data/alpha.local"

tls:
  cert_file: "./certs/alpha.local.crt"
  key_file: "./certs/alpha.local.key"
  ca_file: "./certs/ca.crt"

s2s:
  peers:
    - domain: "beta.local"
      host: "127.0.0.1"
      port: 8002
  shared_secret: "s2s-shared-secret-key"

security:
  jwt_secret: "alpha-jwt-secret-key"
  jwt_access_expire_minutes: 30
  jwt_refresh_expire_days: 7
  bcrypt_cost: 12
  max_login_attempts_ip: 5
  ip_lockout_minutes: 15
  max_login_attempts_account: 10
  account_lockout_minutes: 30
  max_send_per_minute: 10
  max_send_per_hour: 60
  max_connections_per_ip: 50
  max_message_size_mb: 15
  recall_window_minutes: 5

intelligence:
  categories: ["工作", "通知", "广告/营销", "社交", "其他"]
  keyword_top_n: 5
  fuzzy_max_distance: 2
  ngram_size: 3
```

---

## 7 TLS 证书方案

开发环境使用自签名证书链：

```
CA Root Certificate (ca.crt / ca.key)
├── alpha.local.crt (server cert)
├── beta.local.crt (server cert)
└── client.crt (可选，用于 mTLS)
```

使用 `cryptography` 库在 `scripts/generate_certs.py` 中自动生成。

---

## 8 错误处理策略

- 所有异常统一在协议层捕获，返回标准错误响应
- 区分业务错误（4xx）与系统错误（5xx）
- 系统错误记录完整堆栈到审计日志
- 客户端对网络断连自动重试（最多 3 次，指数退避）

---

## 9 并发模型

- 服务端：单进程 asyncio 事件循环
- 每个客户端连接对应一个 asyncio Task
- SQLite 通过 `aiosqlite` 实现异步访问
- 写操作通过队列序列化，避免 SQLite 锁冲突
- 目标：单实例支持 ≥ 100 并发连接

---

## 10 依赖清单

```
# requirements.txt
aiosqlite>=0.19.0
bcrypt>=4.1.0
PyJWT>=2.8.0
cryptography>=41.0.0
jieba>=0.42.1
pyyaml>=6.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
```
