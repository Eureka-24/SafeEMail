# SafeEmail 智能安全邮箱系统

> 一个基于 Python asyncio 的安全邮箱系统，支持双域名、TLS 加密、智能分类与审计日志。

## 项目概述

SafeEmail 是一个完整的邮箱系统实现，包含：
- **服务端**：asyncio TCP 服务器，支持双域名隔离运行
- **客户端**：异步 TCP 连接管理，支持 TLS 加密通信
- **智能引擎**：DeepSeek API 邮件分类（朴素贝叶斯 Fallback）、TF-IDF 关键词提取、模糊搜索
- **安全防护**：TLS 1.3、JWT 鉴权、bcrypt 密码哈希、HMAC 签名、XSS 防护、钓鱼检测
- **审计日志**：所有关键操作全量审计追踪

## 快速开始

### 1. 环境要求

- Python 3.10+
- SQLite 3（内置）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 生成 TLS 证书

```bash
python scripts/generate_certs.py
```

将在 `certs/` 目录下生成 CA 根证书和 alpha.local/beta.local 的服务器证书。

### 4. 配置 DeepSeek API（可选）

在 `config/alpha.env` 和 `config/beta.env` 中配置 API Key：

```
DEEPSEEK_API_KEY=your-api-key-here
```

未配置时自动降级为朴素贝叶斯分类器。

### 5. 启动服务器

**方式一：一键启动双域名服务器**

```bash
python scripts/start_servers.py
```

**方式二：分别启动**

```bash
# Alpha 服务器 (端口 8001)
python -m server.main config/alpha.yaml

# Beta 服务器 (端口 8002)
python -m server.main config/beta.yaml
```

### 6. 运行测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行特定模块测试
python -m pytest tests/test_auth.py -v        # 认证测试
python -m pytest tests/test_mail.py -v        # 邮件测试
python -m pytest tests/test_relay.py -v       # 跨域中继测试
python -m pytest tests/test_security.py -v    # 安全测试
python -m pytest tests/test_concurrent.py -v  # 并发测试
python -m pytest tests/test_audit.py -v       # 审计日志测试
```

## 项目结构

```
SafeEmail/
├── server/                      # 服务端
│   ├── main.py                  # 服务器启动入口
│   ├── config.py                # 配置管理 (YAML)
│   ├── protocol/                # 协议层
│   │   ├── handler.py           # 消息路由与分发
│   │   └── codec.py             # JSON 编解码 (\r\n 分隔)
│   ├── auth/                    # 认证模块
│   │   ├── service.py           # 注册/登录/登出/Token
│   │   ├── jwt_util.py          # JWT 签发与验证
│   │   ├── password.py          # bcrypt 密码哈希
│   │   └── rate_limiter.py      # 暴力破解防护
│   ├── mail/                    # 邮件模块
│   │   ├── service.py           # 邮件收发/撤回/草稿/群发
│   │   ├── relay.py             # S2S 跨域中继
│   │   ├── group.py             # 群组管理
│   │   └── quick_reply.py       # 快速回复建议
│   ├── storage/                 # 存储引擎
│   │   ├── database.py          # SQLite (WAL 模式)
│   │   ├── attachment.py        # 附件存储与去重
│   │   └── migrations.py        # 数据库建表迁移
│   ├── security/                # 安全防护
│   │   ├── tls.py               # TLS 配置
│   │   ├── sanitizer.py         # HTML 清洗/XSS 防护
│   │   ├── spam_detector.py     # 钓鱼/垃圾邮件检测
│   │   └── rate_limit.py        # 发送频率限流
│   ├── intelligence/            # 智能引擎
│   │   ├── classifier.py        # DeepSeek + 朴素贝叶斯分类
│   │   ├── keyword_extractor.py # TF-IDF 关键词提取
│   │   ├── search_engine.py     # 倒排索引 + 模糊搜索
│   │   └── action_engine.py     # 快捷操作引擎
│   └── audit/                   # 审计日志
│       └── logger.py            # 审计日志记录
├── client/                      # 客户端
│   ├── connection.py            # TCP 连接管理 (TLS)
│   ├── commands/                # 用户命令处理
│   └── ui/                      # 界面层
├── shared/                      # 共享模块
│   ├── protocol.py              # Action 枚举/消息构造/状态码
│   └── crypto.py                # HMAC/SHA-256 工具
├── scripts/                     # 脚本
│   ├── start_servers.py         # 一键启动双服务器
│   └── generate_certs.py        # 生成 TLS 证书
├── config/                      # 配置
│   ├── alpha.yaml / alpha.env   # Alpha 服务器配置
│   └── beta.yaml / beta.env     # Beta 服务器配置
├── tests/                       # 测试 (130+ 测试用例)
│   ├── test_m1_framework.py     # M1: 基础框架
│   ├── test_m1_tls.py           # M1: TLS 通信
│   ├── test_auth.py             # M2: 用户认证
│   ├── test_mail.py             # M3: 核心邮件
│   ├── test_relay.py            # M4: 跨域中继
│   ├── test_attachment.py       # M5: 附件存储
│   ├── test_security.py         # M6: 安全加固
│   ├── test_intelligence.py     # M7: 智能功能
│   ├── test_quick_action.py     # M8: 快捷操作
│   ├── test_concurrent.py       # M9: 并发测试
│   └── test_audit.py            # M9: 审计日志
├── docs/
│   ├── PRD.md                   # 产品需求文档
│   ├── SPEC.md                  # 技术规格说明书
│   └── TODO.md                  # 开发计划追踪
└── requirements.txt
```

## 功能清单

| 模块 | 功能 | 状态 |
|------|------|------|
| 基础框架 | TCP 通信 + TLS 加密 + 双域名服务器 | ✅ |
| 用户认证 | 注册/登录/登出/Token 续期/防暴力破解 | ✅ |
| 核心邮件 | 发送/收件箱/发件箱/草稿/群发/群组/撤回 | ✅ |
| 跨域中继 | S2S TLS 通信 + HMAC 签名 + 跨域撤回 | ✅ |
| 附件存储 | 上传/下载/SHA-256 去重/HMAC 完整性 | ✅ |
| 安全加固 | 频率限流/钓鱼检测/XSS 防护/撤回核验 | ✅ |
| 智能引擎 | 关键词提取/邮件分类/模糊搜索 | ✅ |
| 快捷操作 | 快速回复/日程/确认拒绝/安全链接/摘要 | ✅ |
| 审计日志 | 全量操作审计 + JSON 格式 + 分级记录 | ✅ |

## 测试覆盖

共 **130+** 个测试用例，覆盖：

- 功能联通：跨域收发、注册登录全流程、邮件撤回、附件收发、群发
- 并发稳定：20 客户端并发、高频发送压力
- 安全防护：暴力登录、发送限流、钓鱼识别、XSS 防护、伪造撤回
- 附件存储：去重验证、删除引用计数、篡改检测
- 审计日志：日志完整性、格式规范性、级别正确性

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 网络 | asyncio + TCP Socket |
| 数据库 | SQLite (WAL 模式) |
| 加密 | TLS 1.3 / JWT / bcrypt / HMAC-SHA256 |
| 分词 | jieba |
| 分类 | DeepSeek API (Fallback: 朴素贝叶斯) |
| 测试 | pytest + pytest-asyncio |
