# SafeEmail 智能安全邮箱系统

> 一个从零构建的安全邮箱系统，包含 Python asyncio 后端 + React Web 前端，支持双域名隔离、TLS 加密、智能分类与端到端审计。

## 项目概述

SafeEmail 是一个完整的智能安全邮箱系统，包含后端服务与 Web 前端客户端：

- **后端服务**：asyncio TCP 服务器，支持双域名隔离运行（alpha.local / beta.local）
- **WebSocket 网关**：Python asyncio 桥接浏览器与后端 TCP 协议
- **Web 前端**：React 19 + TypeScript + Ant Design 6，现代化邮箱界面
- **智能引擎**：DeepSeek API 邮件分类（朴素贝叶斯 Fallback）、TF-IDF 关键词提取、模糊搜索
- **安全防护**：TLS 1.3、JWT 鉴权、bcrypt 密码哈希、HMAC 签名、XSS 防护、钓鱼检测、多维限流
- **审计日志**：所有关键操作全量审计追踪

### 系统架构

```
浏览器 (React SPA)
    │
    │  WebSocket (ws://localhost:3001 或 3002)
    │
WebSocket 网关 (Python asyncio)
    │
    │  TCP + TLS (localhost:8001 或 8002)
    │
SafeEmail 后端服务器 (alpha.local / beta.local)
```

## 快速开始

### 1. 环境要求

- **Python 3.10+**
- **Node.js 18+**（前端开发）
- **SQLite 3**（内置）

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 安装前端依赖

```bash
cd web
npm install
```

### 4. 生成 TLS 证书

```bash
python scripts/generate_certs.py
```

将在 `certs/` 目录下生成 CA 根证书和 alpha.local/beta.local 的服务器证书。

### 5. 配置 DeepSeek API（可选）

在 `config/alpha.env` 和 `config/beta.env` 中配置 API Key：

```env
DEEPSEEK_API_KEY=your-api-key-here
```

未配置时系统自动降级为朴素贝叶斯分类器。

### 6. 启动全部服务

**方式一：一键启动（推荐）**

双击运行或命令行执行：

```bash
# Windows
scripts\start_all.bat

# Linux/macOS
python scripts/start_all.py
```

启动脚本将打开 6 个独立终端窗口，分别运行：

| 服务 | 地址 | 说明 |
|------|------|------|
| Alpha 后端 | `127.0.0.1:8001` | TCP + TLS 服务器 |
| Beta 后端 | `127.0.0.1:8002` | TCP + TLS 服务器 |
| Alpha WS 网关 | `ws://127.0.0.1:3001` | 浏览器 → Alpha 后端桥接 |
| Beta WS 网关 | `ws://127.0.0.1:3002` | 浏览器 → Beta 后端桥接 |
| Alpha 前端 | `http://localhost:5173` | Web 客户端（Alpha 域名） |
| Beta 前端 | `http://localhost:5174` | Web 客户端（Beta 域名） |

**方式二：分步启动**

```bash
# 1. 启动后端
python server/main.py config/alpha.yaml
python server/main.py config/beta.yaml

# 2. 启动 WebSocket 网关
python server/ws_gateway.py config/alpha.yaml
python server/ws_gateway.py config/beta.yaml

# 3. 启动前端（另开终端）
cd web && npx vite --mode alpha --port 5173
cd web && npx vite --mode beta --port 5174
```

### 7. 访问前端

打开浏览器访问：
- **Alpha 实例**：http://localhost:5173
- **Beta 实例**：http://localhost:5174

在登录页面可以注册新账号（用户名 ≥ 3 字符，密码 ≥ 8 位含大小写+数字），注册后登录即可使用完整邮箱功能。

### 8. 停止服务

**Windows**：运行 `scripts\stop_all.bat` 或逐个关闭终端窗口

**Linux/macOS**：在启动脚本终端按 `Ctrl+C`

### 9. 运行测试

```bash
# 运行全部测试（130+ 用例）
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
│   ├── ws_gateway.py            # WebSocket 网关（浏览器 ↔ TCP 桥接）
│   ├── protocol/                # 协议层
│   │   ├── handler.py           # 消息路由与分发
│   │   ├── codec.py             # JSON 编解码 (\r\n 分隔)
│   │   └── actions.py           # Action 常量定义
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
│   │   ├── models.py            # 数据访问层
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
├── client/                      # 命令行客户端（legacy）
│   ├── connection.py            # TCP 连接管理 (TLS)
│   ├── commands/                # 用户命令处理
│   └── ui/                      # 界面层
├── shared/                      # 共享模块
│   ├── protocol.py              # Action 枚举/消息构造/状态码
│   └── crypto.py                # HMAC/SHA-256 工具
├── web/                         # Web 前端
│   ├── src/
│   │   ├── main.tsx             # 入口
│   │   ├── App.tsx              # 根组件 + 路由
│   │   ├── config.ts            # 环境配置
│   │   ├── api/
│   │   │   ├── ws.ts            # WebSocket 连接管理
│   │   │   ├── protocol.ts      # 协议消息构造
│   │   │   └── client.ts        # 高层 API 封装
│   │   ├── stores/
│   │   │   ├── authStore.ts     # 认证状态
│   │   │   ├── mailStore.ts     # 邮件状态
│   │   │   └── uiStore.ts       # UI 状态
│   │   ├── pages/               # 页面组件
│   │   ├── components/          # 通用组件
│   │   ├── hooks/               # React Hooks
│   │   ├── utils/               # 工具函数
│   │   └── types/               # TypeScript 类型定义
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── scripts/
│   ├── start_all.py             # 一键启动（Python 版）
│   ├── start_all.bat            # 一键启动（Windows 批处理）
│   ├── stop_all.bat             # 一键停止（Windows 批处理）
│   ├── start_servers.py         # 一键启动双服务器（legacy）
│   └── generate_certs.py        # 生成 TLS 证书
├── config/
│   ├── alpha.yaml / alpha.env   # Alpha 服务器配置
│   └── beta.yaml / beta.env     # Beta 服务器配置
├── web/
│   ├── .env.alpha               # Alpha 前端环境变量
│   └── .env.beta                # Beta 前端环境变量
├── tests/                       # 测试（130+ 测试用例）
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
│   ├── PRD.md                   # 后端产品需求文档
│   ├── SPEC.md                  # 后端技术规格说明书
│   ├── PROTOCOL.md              # 通信协议说明
│   ├── TODO.md                  # 后端开发计划追踪
│   ├── THREAT_MODEL.md          # 威胁模型说明
│   ├── FRONTEND_PRD.md          # 前端产品需求文档
│   ├── FRONTEND_SPEC.md         # 前端技术规格说明书
│   └── FRONTEND_TODO.md         # 前端开发计划追踪
└── requirements.txt
```

## 功能清单

### 后端（M1–M10 全部完成）

| 模块 | 功能 | 状态 |
|------|------|------|
| 基础框架 | TCP 通信 + TLS 加密 + 双域名服务器 | ✅ |
| 用户认证 | 注册/登录/登出/Token 续期/防暴力破解/验证码 | ✅ |
| 核心邮件 | 发送/收件箱/发件箱/草稿/群发/群组/撤回 | ✅ |
| 跨域中继 | S2S TLS 通信 + HMAC 签名 + 跨域撤回 | ✅ |
| 附件存储 | 上传/下载/SHA-256 去重/HMAC 完整性 | ✅ |
| 安全加固 | 频率限流/钓鱼检测/XSS 防护/撤回核验 | ✅ |
| 智能引擎 | 关键词提取/邮件分类/模糊搜索 | ✅ |
| 快捷操作 | 快速回复/日程/确认拒绝/安全链接/摘要 | ✅ |
| 审计日志 | 全量操作审计 + JSON 格式 + 分级记录 | ✅ |

### 前端（F1–F5 全部完成）

| 模块 | 功能 | 状态 |
|------|------|------|
| 基础框架 | Vite + React + TypeScript + Ant Design | ✅ |
| WebSocket 通信 | 连接管理/自动重连/心跳保活/请求匹配 | ✅ |
| 认证模块 | 登录/注册/Token 自动续期/验证码弹窗 | ✅ |
| 邮件核心 | 收件箱/发件箱/草稿箱/邮件详情/写邮件 | ✅ |
| 高级功能 | 搜索/撤回倒计时/附件上传下载/快速回复 | ✅ |
| 群组管理 | 群组列表/创建群组/写邮件时群组选择 | ✅ |
| 安全提示 | 垃圾邮件标识/发送警告/限流提示 | ✅ |
| 交互打磨 | 网络断开警告/骨架屏/空状态/Toast 通知 | ✅ |

## 通信协议

系统采用自定义 JSON 协议 over TCP（后端）和 WebSocket（前端 ↔ 网关），每条消息以 `\r\n` 分隔。

### 请求消息格式

```json
{
  "version": "1.0",
  "type": "REQUEST",
  "action": "SEND_MAIL",
  "request_id": "<uuid4>",
  "token": "<JWT Access Token | null>",
  "payload": { ... }
}
```

### 响应消息格式

```json
{
  "version": "1.0",
  "type": "RESPONSE",
  "request_id": "<uuid4>",
  "status": 200,
  "message": "操作成功",
  "payload": { ... }
}
```

完整协议文档见 [docs/PROTOCOL.md](docs/PROTOCOL.md)。

## 前端技术栈

| 层面 | 技术选型 | 说明 |
|------|----------|------|
| 框架 | React 19 + TypeScript | 组件化、类型安全 |
| 构建工具 | Vite 8 | 极速 HMR |
| UI 组件库 | Ant Design 6 | 企业级组件 |
| 路由 | React Router v7 | SPA 路由管理 |
| 状态管理 | Zustand 5 | 轻量、TypeScript 友好 |
| 富文本编辑 | TipTap 3 | 邮件正文编辑器 |
| HTML 清洗 | DOMPurify 3 | XSS 防护 |
| WebSocket | 原生 WebSocket | 与网关直连 |

## 安全设计

### Token 安全
- `access_token` 和 `refresh_token` 仅存储在 JavaScript 内存（Zustand store）
- **不写入** localStorage / sessionStorage / cookie
- 页面刷新后 Token 丢失，用户需重新登录（安全优先策略）
- 过期前 2 分钟自动续期

### XSS 防护
- 邮件正文通过 DOMPurify 二次清洗后渲染
- 富文本编辑器输出 HTML，发送前后端再次清洗

### HMAC 签名
- **撤回签名**：由后端在 `LIST_SENT` / `READ_MAIL` 响应中预生成 `recall_signature` 下发
- **快捷操作签名**：由后端在邮件 `actions` 字段中预生成，前端直接回传
- 前端不持有 `jwt_secret`，无法伪造签名

### 传输安全
- 后端与 WebSocket 网关之间：TCP + TLS 1.3
- 浏览器与 WebSocket 网关之间：WebSocket（ws://），网关承担 TLS 桥接角色

## 双域名实例

系统同时运行两个独立的服务器实例，模拟两个隔离域名：

| 实例 | 后端端口 | WS 网关端口 | 前端端口 | 数据目录 |
|------|----------|-------------|----------|----------|
| Alpha | 8001 | 3001 | 5173 | `data/alpha.local/` |
| Beta | 8002 | 3002 | 5174 | `data/beta.local/` |

两个实例数据完全隔离，通过 S2S 中继协议实现跨域邮件投递。

## 测试覆盖

共 **130+** 个测试用例，覆盖：

- **功能联通**：跨域收发、注册登录全流程、邮件撤回、附件收发、群发
- **并发稳定**：20 客户端并发、高频发送压力
- **安全防护**：暴力登录、发送限流、钓鱼识别、XSS 防护、伪造撤回
- **附件存储**：去重验证、删除引用计数、篡改检测
- **审计日志**：日志完整性、格式规范性、级别正确性

## 开发里程碑

### 后端（M1–M10，已全部完成）

```
M1 (基础框架) → M2 (认证) → M3 (邮件) → M4 (跨域中继)
                    ↓                          ↓
               M6 (安全加固)              M5 (附件存储)
                    ↓                          ↓
               M7 (智能功能) ──────────→ M8 (快捷操作)
                                              ↓
                                        M9 (测试验收) → M10 (文档交付)
```

### 前端（F1–F5，已全部完成）

```
F1 (基础框架+认证) → F2 (邮件核心) → F3 (高级功能)
                                          ↓
                                    F4 (群组+安全提示)
                                          ↓
                                    F5 (打磨+启动脚本)
```

## 文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 后端 PRD | [docs/PRD.md](docs/PRD.md) | 产品需求文档 |
| 后端 SPEC | [docs/SPEC.md](docs/SPEC.md) | 技术规格说明书 |
| 协议文档 | [docs/PROTOCOL.md](docs/PROTOCOL.md) | 通信协议说明 |
| 威胁模型 | [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | 安全威胁分析 |
| 后端 TODO | [docs/TODO.md](docs/TODO.md) | 开发计划追踪 |
| 前端 PRD | [docs/FRONTEND_PRD.md](docs/FRONTEND_PRD.md) | 前端产品需求文档 |
| 前端 SPEC | [docs/FRONTEND_SPEC.md](docs/FRONTEND_SPEC.md) | 前端技术规格说明书 |
| 前端 TODO | [docs/FRONTEND_TODO.md](docs/FRONTEND_TODO.md) | 前端开发计划追踪 |

## 风险与注意事项

1. **SQLite 并发写入**：使用 WAL 模式 + 写操作队列序列化，避免锁冲突
2. **大附件 Base64 传输**：15MB 限制 → Base64 后约 20MB，注意浏览器内存
3. **WebSocket 网关单点**：单 asyncio 进程，预计支持 50+ 并发连接，满足开发演示需求
4. **富文本安全**：用户输入 HTML 发送前无需前端清洗（后端已处理），但显示其他用户邮件时需 DOMPurify 二次清洗
5. **Token 持久化**：刷新页面丢失 Token（安全设计），用户需重新登录
6. **jieba 首次加载**：首次分词有加载延迟，建议服务启动时预热

## License

本项目仅供学习和研究使用。
