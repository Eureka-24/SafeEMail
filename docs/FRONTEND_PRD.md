# SafeEmail 前端产品需求文档（PRD）

| 字段     | 内容                              |
| -------- | --------------------------------- |
| 产品名称 | SafeEmail Web 客户端              |
| 文档版本 | v1.0                              |
| 创建日期 | 2026-04-21                        |
| 关联文档 | docs/SPEC.md · docs/PROTOCOL.md   |

---

## 1 项目概述

### 1.1 背景

SafeEmail 后端已完成 M1–M10 全部里程碑，提供了基于 TCP + TLS 的自定义 JSON 协议。现需构建 Web 前端，使用户通过浏览器即可完成邮箱的全部操作。

### 1.2 目标

- 提供完整的 Web 邮箱客户端，覆盖后端所有面向用户的 Action
- 支持双域名实例：alpha.local 和 beta.local 各自独立部署前端，共用同一套代码
- 通过 **WebSocket 网关**桥接浏览器与后端 TCP 协议（浏览器无法直接发起 TCP 连接）
- 界面现代化、响应式，参考主流邮箱（Gmail/Outlook）交互范式

### 1.3 核心原则

| 原则     | 说明 |
| -------- | ---- |
| 协议透传 | 前端构造的 JSON 消息格式与 PROTOCOL.md 完全一致，网关层仅做 WebSocket ↔ TCP 转发 |
| 域名隔离 | 每个域名实例的前端通过配置连接不同的 WebSocket 网关端口，数据完全隔离 |
| 设计复用 | alpha 和 beta 共用同一份前端源码，仅通过环境变量区分连接目标 |
| 安全优先 | Token 存储于内存（非 localStorage），支持自动续期，敏感操作二次确认 |

---

## 2 系统架构

### 2.1 整体架构

```
浏览器 (React SPA)
    │
    │  WebSocket (ws://localhost:3001 或 3002)
    │
WebSocket 网关 (Python asyncio)
    │
    │  TCP + TLS (localhost:8001 或 8002)
    │
SafeEmail 后端服务器
```

### 2.2 WebSocket 网关

新增一个轻量 Python 脚本 `server/ws_gateway.py`，职责：

1. 监听 WebSocket 端口（alpha → 3001，beta → 3002）
2. 每个 WebSocket 连接对应一条到后端的 TCP 连接
3. **透传协议**：将浏览器发来的 JSON 原样转发到 TCP 后端，将 TCP 响应原样回传浏览器
4. 消息分界：WebSocket 帧本身有边界，TCP 侧沿用 `\r\n` 分隔
5. 连接生命周期管理：WebSocket 断开时关闭 TCP 连接

### 2.3 前端技术栈

| 层面       | 选型                           | 说明                        |
| ---------- | ------------------------------ | --------------------------- |
| 框架       | React 18 + TypeScript          | 组件化、类型安全             |
| 构建工具   | Vite                           | 极速 HMR，开箱即用           |
| UI 组件库  | Ant Design 5                   | 成熟的企业级组件，邮箱适配好 |
| 路由       | React Router v6                | SPA 路由管理                |
| 状态管理   | Zustand                        | 轻量、TypeScript 友好       |
| 通信       | 原生 WebSocket                 | 与网关直连                  |
| 富文本编辑 | React Quill 或 TipTap          | 邮件正文编辑器              |
| 图标       | @ant-design/icons              | 与 Ant Design 配套          |

### 2.4 项目结构

```
web/
├── public/
│   └── favicon.ico
├── src/
│   ├── main.tsx                    # 入口
│   ├── App.tsx                     # 根组件 + 路由
│   ├── config.ts                   # 环境配置（WS 地址、域名）
│   ├── api/
│   │   ├── ws.ts                   # WebSocket 连接管理
│   │   ├── protocol.ts             # 协议消息构造（与 shared/protocol.py 对齐）
│   │   └── client.ts               # 高层 API 封装（login/sendMail/...）
│   ├── stores/
│   │   ├── authStore.ts            # 认证状态（token/user/domain）
│   │   ├── mailStore.ts            # 邮件列表/当前邮件
│   │   └── uiStore.ts              # UI 状态（侧边栏/主题/加载）
│   ├── pages/
│   │   ├── LoginPage.tsx           # 登录/注册页
│   │   ├── InboxPage.tsx           # 收件箱
│   │   ├── SentPage.tsx            # 发件箱
│   │   ├── DraftPage.tsx           # 草稿箱
│   │   ├── MailDetailPage.tsx      # 邮件详情/阅读
│   │   ├── ComposePage.tsx         # 写邮件/回复/转发
│   │   ├── SearchPage.tsx          # 搜索结果
│   │   └── GroupPage.tsx           # 群组管理
│   ├── components/
│   │   ├── Layout/
│   │   │   ├── AppLayout.tsx       # 整体布局（侧边栏 + 顶栏 + 内容区）
│   │   │   ├── Sidebar.tsx         # 侧边导航
│   │   │   └── Header.tsx          # 顶栏（搜索框/用户信息/登出）
│   │   ├── Mail/
│   │   │   ├── MailList.tsx        # 邮件列表组件
│   │   │   ├── MailListItem.tsx    # 单封邮件摘要行
│   │   │   ├── MailViewer.tsx      # 邮件正文查看
│   │   │   ├── ComposeForm.tsx     # 写邮件表单
│   │   │   ├── AttachmentBar.tsx   # 附件栏（上传/下载/预览）
│   │   │   ├── QuickReplyBar.tsx   # 快速回复建议条
│   │   │   └── ActionButtons.tsx   # 快捷操作按钮组
│   │   ├── Auth/
│   │   │   ├── LoginForm.tsx       # 登录表单
│   │   │   ├── RegisterForm.tsx    # 注册表单
│   │   │   └── CaptchaModal.tsx    # 验证码弹窗
│   │   ├── Group/
│   │   │   ├── GroupList.tsx       # 群组列表
│   │   │   └── GroupForm.tsx       # 创建群组表单
│   │   └── Common/
│   │       ├── SpamBadge.tsx       # 垃圾邮件标记
│   │       ├── RecallButton.tsx    # 撤回按钮（含倒计时）
│   │       └── EmptyState.tsx      # 空状态提示
│   ├── hooks/
│   │   ├── useWebSocket.ts         # WebSocket 连接 Hook
│   │   ├── useAuth.ts              # 认证相关 Hook
│   │   └── useMail.ts             # 邮件操作 Hook
│   ├── utils/
│   │   ├── hmac.ts                 # HMAC-SHA256 签名（用于撤回/快捷操作）
│   │   ├── format.ts              # 日期/文件大小格式化
│   │   └── validators.ts          # 密码/用户名校验规则
│   └── types/
│       ├── protocol.ts            # 协议类型定义
│       ├── mail.ts                # 邮件相关类型
│       └── auth.ts                # 认证相关类型
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
└── .env.alpha / .env.beta          # 环境配置
```

---

## 3 功能模块详细设计

### 3.1 认证模块

#### P1: 登录页

| 项目 | 说明 |
| ---- | ---- |
| 路由 | `/login` |
| 布局 | 居中卡片，显示当前域名标识（如 "alpha.local 邮箱"） |

**交互流程：**

1. 用户输入用户名 + 密码，点击"登录"
2. 前端构造 `LOGIN` 消息，通过 WebSocket 发送
3. 成功：存储 `access_token`（内存）和 `refresh_token`，跳转收件箱
4. 失败（401）：显示错误提示
5. 需要验证码（`captcha_required: true`）：弹出验证码弹窗，用户输入后附加 `captcha_answer` 字段重新提交
6. 被限流（429）：显示"操作过于频繁，请稍后再试"，按钮禁用并倒计时

**表单校验（前端预校验）：**

- 用户名：≥ 3 字符
- 密码：≥ 8 位，包含大写 + 小写 + 数字

#### P2: 注册页

| 项目 | 说明 |
| ---- | ---- |
| 路由 | `/register` |
| 布局 | 同登录页，Tab 切换 |

**字段：**
- 用户名（≥ 3 字符）
- 密码（≥ 8 位，大写+小写+数字）
- 确认密码（一致性校验）

**成功后**自动跳转登录页，提示"注册成功，请登录"。

#### P3: Token 自动续期

- 前端维护 `access_token` 的过期时间（从 JWT payload 解析 `exp`）
- 在过期前 2 分钟自动发送 `REFRESH` 请求获取新 Token
- 续期失败则跳转登录页

#### P4: 登出

- 顶栏右上角"登出"按钮
- 发送 `LOGOUT` 请求，清除内存中的 Token
- 跳转登录页

---

### 3.2 邮件核心模块

#### P5: 收件箱

| 项目 | 说明 |
| ---- | ---- |
| 路由 | `/inbox` （默认页） |
| Action | `LIST_INBOX` |

**界面设计：**

```
┌──────────┬──────────────────────────────────────────┐
│ 侧边栏   │  收件箱                          🔍搜索  │
│          │──────────────────────────────────────────│
│ 📥 收件箱 │  ● alice@beta  会议通知        10:30 AM │
│ 📤 发件箱 │    bob@alpha   项目进度更新      9:15 AM │
│ 📝 草稿箱 │  ⚠️ unknown    【垃圾】中奖通知  8:00 AM │
│ 👥 群组   │                                        │
│          │              < 1  2  3 >                 │
└──────────┴──────────────────────────────────────────┘
```

**功能点：**
- 邮件列表：显示发件人、主题、时间、已读/未读状态
- 未读邮件加粗显示，已读邮件灰色
- 垃圾邮件标记：`is_spam = true` 的邮件显示 ⚠️ 警告标签
- 分页：底部分页器，默认 20 条/页
- 点击邮件行 → 进入邮件详情页
- 已撤回邮件不显示（后端已过滤）

#### P6: 发件箱

| 项目 | 说明 |
| ---- | ---- |
| 路由 | `/sent` |
| Action | `LIST_SENT` |

**功能点：**
- 邮件列表：显示收件人、主题、发送时间、状态（SENT/RECALLED）
- 已撤回邮件显示 "已撤回" 标签（灰色斜体）
- 点击 → 邮件详情页
- SENT 状态的邮件：若在 5 分钟撤回窗口内，显示"撤回"按钮（含倒计时）

#### P7: 草稿箱

| 项目 | 说明 |
| ---- | ---- |
| 路由 | `/drafts` |
| Action | `LIST_DRAFTS` |

**功能点：**
- 草稿列表：显示收件人、主题、最后修改时间
- 点击 → 跳转写邮件页（预填草稿内容，携带 `draft_id`）
- 支持删除草稿（前端标记，或后续后端扩展）

#### P8: 邮件详情/阅读

| 项目 | 说明 |
| ---- | ---- |
| 路由 | `/mail/:emailId` |
| Action | `READ_MAIL` |

**界面设计：**

```
┌─────────────────────────────────────────────┐
│  ← 返回    会议通知              撤回 🔄     │
│─────────────────────────────────────────────│
│  From: alice@beta.local                     │
│  To: bob@alpha.local, carol@alpha.local     │
│  Time: 2026-04-21 10:30 AM                 │
│─────────────────────────────────────────────│
│                                             │
│  明天下午3点在B2会议室开项目评审会议，        │
│  请确认是否参加。                            │
│                                             │
│  📎 附件: 会议议程.pdf (128KB) [下载]        │
│─────────────────────────────────────────────│
│  快捷操作:                                   │
│  [📅 添加日程: 评审] [✅ 确认] [❌ 拒绝]      │
│  [📋 复制摘要]                               │
│─────────────────────────────────────────────│
│  快速回复:                                   │
│  [好的，我准时参加。]  [收到，会议时间没问题。]│
│  [了解，请提前发会议链接。]                   │
│─────────────────────────────────────────────│
│            [回复]  [转发]                     │
└─────────────────────────────────────────────┘
```

**功能点：**
- 邮件头：发件人、收件人、时间
- 邮件正文：HTML 渲染（后端已清洗，前端使用 `dangerouslySetInnerHTML` 或 iframe 沙箱）
- 附件区：列出附件列表，支持下载（`DOWNLOAD_ATTACH`）和图片预览
- 快捷操作按钮（ActionButtons）：从邮件的 `actions` 字段渲染，点击触发 `EXEC_ACTION`
  - `schedule` → 直接执行，Toast 提示"已添加日程"
  - `confirm/reject` → 弹出二次确认对话框
  - `safe_link` → 安全则新窗口打开，不安全则警告拦截
  - `summary` → 复制到剪贴板
- 快速回复建议（QuickReplyBar）：调用 `QUICK_REPLY` 获取建议，点击建议 → 跳转写邮件页并预填
- 撤回按钮：仅当前用户是发件人且在 5 分钟窗口内显示

#### P9: 写邮件

| 项目 | 说明 |
| ---- | ---- |
| 路由 | `/compose`、`/compose?reply=<emailId>`、`/compose?draft=<draftId>` |
| Action | `SEND_MAIL`、`SAVE_DRAFT`、`UPLOAD_ATTACH` |

**界面设计：**

```
┌─────────────────────────────────────────────┐
│  写邮件                      [保存草稿] [发送]│
│─────────────────────────────────────────────│
│  To:    [bob@beta.local, carol@alpha.local] │
│         👥 从群组选择                        │
│  Subject: [Re: 会议通知                   ] │
│─────────────────────────────────────────────│
│  ┌─────────────────────────────────────┐    │
│  │ 富文本编辑器                        │    │
│  │ B I U  | 🔗 | 📷                   │    │
│  │                                     │    │
│  │ 好的，我准时参加。                   │    │
│  │                                     │    │
│  └─────────────────────────────────────┘    │
│  📎 附件: [+ 添加附件]                       │
│     会议议程.pdf (128KB)  ✕                  │
└─────────────────────────────────────────────┘
```

**功能点：**
- 收件人输入：支持多个地址（逗号/回车分隔），支持 `user` 或 `user@domain` 格式
- 群组选择：点击"从群组选择"按钮，弹出群组列表（`LIST_GROUPS`），选择后展开为成员地址
- 主题输入
- 富文本编辑器：支持加粗/斜体/链接/图片插入
- 附件上传：支持拖拽或点击上传，Base64 编码后通过 `UPLOAD_ATTACH` 上传，显示文件名和大小
- 保存草稿：定时自动保存（每 30 秒） + 手动保存按钮，调用 `SAVE_DRAFT`
- 发送：调用 `SEND_MAIL`
  - 成功：Toast 提示"发送成功"，跳转发件箱
  - 垃圾邮件警告：若响应包含 `spam_warning`，弹窗提示并显示原因
  - 限流（429）：提示"发送过于频繁"

**回复模式（`/compose?reply=<emailId>`）：**
- 自动填充收件人（原发件人）
- 自动填充主题（`Re: 原主题`）
- 正文底部引用原文

**草稿模式（`/compose?draft=<draftId>`）：**
- 预填草稿内容
- 更新时传递 `draft_id`

#### P10: 邮件撤回

| 项目 | 说明 |
| ---- | ---- |
| Action | `RECALL_MAIL` |

**交互流程：**
1. 发件箱/邮件详情中，5 分钟窗口内的已发送邮件显示"撤回"按钮
2. 按钮旁显示倒计时（如"还剩 3:24"）
3. 点击撤回 → 弹出确认对话框
4. 前端计算 HMAC 签名：`HMAC-SHA256(jwt_secret, "RECALL:{email_id}:{from_user}")`
   > 注意：`jwt_secret` 不应暴露给前端。实际实现中，撤回签名应由后端预生成并随邮件数据下发，前端仅回传。
5. 发送 `RECALL_MAIL`
6. 成功：显示"已撤回"，若 `already_read=true` 则额外提示"部分收件人可能已阅读"

**签名方案调整建议：**
由于前端无法安全持有 `jwt_secret`，建议后端在 `LIST_SENT` 和 `READ_MAIL` 响应中为发件人追加 `recall_signature` 字段，前端直接使用。

#### P11: 邮件搜索

| 项目 | 说明 |
| ---- | ---- |
| 路由 | `/search?q=<keyword>` |
| Action | `SEARCH_MAIL` |

**交互流程：**
1. 顶栏搜索框输入关键词，回车或点击搜索
2. 发送 `SEARCH_MAIL` 请求
3. 结果列表展示：邮件 ID、发件人、主题、时间、匹配类型、相关性评分
4. 点击结果 → 跳转邮件详情页
5. 支持模糊搜索（后端处理，前端无需额外逻辑）

---

### 3.3 附件模块

#### P12: 附件上传

| Action | `UPLOAD_ATTACH` |
| ------ | --------------- |

**交互：**
- 写邮件页中，点击"添加附件"或拖拽文件
- 文件转 Base64，通过 `UPLOAD_ATTACH` 上传
- 上传中显示进度条（基于文件大小估算）
- 完成后显示文件名、大小、删除按钮
- 限制：单文件 ≤ 15MB

#### P13: 附件下载与预览

| Action | `DOWNLOAD_ATTACH` |
| ------ | ----------------- |

**交互：**
- 邮件详情中，附件栏列出所有附件
- 点击文件名 → 下载（Base64 解码后触发浏览器下载）
- 图片类附件（image/*）：点击后弹出预览大图
- 显示文件大小和类型图标

---

### 3.4 群组模块

#### P14: 群组管理

| 项目 | 说明 |
| ---- | ---- |
| 路由 | `/groups` |
| Action | `CREATE_GROUP`、`LIST_GROUPS` |

**功能点：**
- 群组列表：显示群组名称、成员数量、成员列表（展开/收起）
- 创建群组：弹窗表单，输入群组名 + 成员地址（多行输入）
- 写邮件时的群组选择器：弹窗列出群组，勾选后自动展开为收件人

---

### 3.5 安全与提示

#### P15: 垃圾邮件提示

- 收件箱中，`is_spam = true` 的邮件：
  - 行前显示 ⚠️ 图标
  - 背景色淡黄/淡红
  - 进入详情后，顶部显示红色警告条："此邮件被检测为垃圾/钓鱼邮件"

#### P16: 发送时垃圾警告

- 发送邮件时，若响应包含 `spam_warning`：
  - 弹出警告对话框，显示 `spam_reasons`
  - 提示"你的邮件被检测到可能包含垃圾/钓鱼内容"
  - 邮件仍然会被发送（后端已处理），但给发件人一个提醒

#### P17: 限流提示

- 登录限流：显示"登录尝试过于频繁，请等待 X 分钟后再试"
- 发送限流：显示"发送频率过高，请稍后再试（限制：10封/分钟，60封/小时）"

#### P18: 验证码

- 登录失败 3 次后，后端返回 `captcha_required: true` 和 `captcha_question`（数学题）
- 前端弹出验证码输入框，用户作答后重新提交登录

---

## 4 页面路由表

| 路由 | 页面 | 需登录 | 说明 |
| ---- | ---- | ------ | ---- |
| `/login` | LoginPage | 否 | 登录/注册 |
| `/register` | LoginPage (tab) | 否 | 注册 |
| `/inbox` | InboxPage | 是 | 收件箱（默认页） |
| `/sent` | SentPage | 是 | 发件箱 |
| `/drafts` | DraftPage | 是 | 草稿箱 |
| `/mail/:id` | MailDetailPage | 是 | 邮件详情 |
| `/compose` | ComposePage | 是 | 写邮件 |
| `/search` | SearchPage | 是 | 搜索结果 |
| `/groups` | GroupPage | 是 | 群组管理 |

---

## 5 WebSocket 通信层设计

### 5.1 连接管理

```typescript
// ws.ts 核心逻辑
class SafeEmailWS {
  private ws: WebSocket;
  private pendingRequests: Map<string, {resolve, reject, timeout}>;

  connect(url: string): Promise<void>;
  send(action: string, payload: object, token?: string): Promise<Response>;
  disconnect(): void;
}
```

**关键设计：**
- **请求-响应匹配**：每个请求携带唯一 `request_id`（UUID v4），通过 `pendingRequests` Map 匹配响应
- **超时机制**：每个请求默认 15 秒超时
- **自动重连**：WebSocket 断开后，指数退避重连（1s → 2s → 4s → 8s，最大 30s）
- **心跳保活**：每 30 秒发送 `PING`，60 秒无响应则触发重连

### 5.2 消息构造

```typescript
// protocol.ts
function buildRequest(action: string, payload: object, token?: string) {
  return {
    version: "1.0",
    type: "REQUEST",
    action,
    request_id: uuid(),
    token: token || null,
    payload
  };
}
```

### 5.3 Token 续期拦截

在 `send()` 方法中：
1. 检查 `access_token` 是否临近过期（< 2 分钟）
2. 若是，先执行 `REFRESH` 获取新 Token
3. 再执行原始请求

---

## 6 WebSocket 网关设计

### 6.1 职责

`server/ws_gateway.py` — 独立于后端主服务运行：

```python
# 伪代码
async def handle_websocket(websocket):
    # 1. 建立到后端的 TCP 连接
    tcp_reader, tcp_writer = await asyncio.open_connection(
        backend_host, backend_port, ssl=ssl_context
    )
    # 2. 双向转发
    await asyncio.gather(
        ws_to_tcp(websocket, tcp_writer),   # 浏览器 → 后端
        tcp_to_ws(tcp_reader, websocket),   # 后端 → 浏览器
    )
```

### 6.2 配置

```yaml
# config/alpha.yaml 新增
ws_gateway:
  host: "127.0.0.1"
  port: 3001              # alpha 网关端口

# config/beta.yaml 新增
ws_gateway:
  host: "127.0.0.1"
  port: 3002              # beta 网关端口
```

### 6.3 启动方式

```bash
# 一键启动（包含后端 + 网关 + 前端 dev server）
python scripts/start_all.py

# 或分步启动
python server/ws_gateway.py config/alpha.yaml   # alpha 网关
python server/ws_gateway.py config/beta.yaml    # beta 网关
cd web && npm run dev                           # 前端开发服务器
```

---

## 7 环境配置与多域名支持

### 7.1 前端环境变量

```bash
# web/.env.alpha
VITE_WS_URL=ws://localhost:3001
VITE_DOMAIN=alpha.local
VITE_APP_TITLE=SafeEmail - Alpha

# web/.env.beta
VITE_WS_URL=ws://localhost:3002
VITE_DOMAIN=beta.local
VITE_APP_TITLE=SafeEmail - Beta
```

### 7.2 启动命令

```bash
# Alpha 前端（端口 5173）
cd web && npx vite --mode alpha --port 5173

# Beta 前端（端口 5174）
cd web && npx vite --mode beta --port 5174
```

---

## 8 UI/UX 设计规范

### 8.1 整体风格

- 配色方案：以蓝色系为主色调（#1677ff），深色侧边栏（#001529）
- 字体：系统默认字体栈（-apple-system, BlinkMacSystemFont, "Segoe UI"）
- 响应式：最小宽度 1024px（桌面端优先），侧边栏可折叠

### 8.2 交互规范

| 场景 | 交互 |
| ---- | ---- |
| 操作成功 | 右上角 Toast 通知（绿色，3秒消失） |
| 操作失败 | 右上角 Toast 通知（红色，5秒消失） |
| 危险操作 | Modal 二次确认（撤回、删除） |
| 加载中 | 按钮显示 Loading 旋转，列表显示骨架屏 |
| 空状态 | 居中图标 + 文案（如"收件箱是空的"） |
| 网络断开 | 顶部全宽黄色警告条："网络连接已断开，正在重连..." |

### 8.3 域名标识

- 登录页和侧边栏顶部明确展示当前域名（如 `alpha.local`）
- 使用不同的主题色区分（可选）：alpha → 蓝色，beta → 绿色

---

## 9 非功能性需求

| 项目 | 要求 |
| ---- | ---- |
| 首屏加载 | < 2 秒（Vite 构建优化） |
| WebSocket 重连 | 断线后自动重连，最大 30 秒退避 |
| Token 安全 | 仅存储于 JavaScript 内存变量，不写入 localStorage/cookie |
| XSS 防护 | 邮件正文通过 iframe sandbox 渲染，或使用 DOMPurify 二次清洗 |
| 浏览器兼容 | Chrome 90+, Firefox 88+, Edge 90+, Safari 14+ |
| 国际化 | 初始版本仅支持中文 |

---

## 10 开发里程碑

### F1 — 基础框架与认证（2 天）
- Vite + React + TypeScript 项目初始化
- Ant Design 集成
- WebSocket 网关（`ws_gateway.py`）
- WebSocket 连接管理（连接/重连/心跳）
- 登录/注册页面
- Token 管理与自动续期
- 路由守卫（未登录跳转）

### F2 — 邮件核心（2 天）
- 整体布局（侧边栏 + 顶栏 + 内容区）
- 收件箱列表与分页
- 发件箱列表
- 草稿箱列表
- 邮件详情阅读页
- 写邮件页（富文本编辑器 + 收件人输入）
- 保存草稿（手动 + 自动）

### F3 — 高级功能（1.5 天）
- 邮件搜索
- 邮件撤回（倒计时 + HMAC 签名）
- 附件上传与下载
- 图片附件预览
- 快速回复建议
- 快捷操作按钮

### F4 — 群组与安全提示（1 天）
- 群组管理页面
- 写邮件时群组选择
- 垃圾邮件警告标识
- 发送时垃圾检测提示
- 限流提示
- 验证码弹窗

### F5 — 打磨与启动脚本（0.5 天）
- 双域名配置验证
- 一键启动脚本（后端 + 网关 + 前端）
- 交互细节打磨（空状态、加载态、错误态）
- 整体冒烟测试

---

## 11 风险与注意事项

1. **HMAC 签名安全**：前端不应持有 `jwt_secret`。撤回签名应由后端预生成随邮件下发，或新增专门的"获取撤回凭证"接口。
2. **大附件传输**：15MB Base64 编码后约 20MB，WebSocket 单帧可能过大。建议分片传输或限制前端上传大小。
3. **WebSocket 网关性能**：单网关进程 asyncio 模型，预计支持 50+ 并发连接，满足开发和演示需求。
4. **富文本编辑器安全**：用户输入的 HTML 在发送前无需清洗（后端 SEND_MAIL 已清洗），但显示其他用户邮件时需谨慎。
5. **CORS**：WebSocket 网关需正确处理跨域请求头（如有需要）。
6. **前端状态持久化**：刷新页面会丢失 Token（安全设计），用户需要重新登录。可考虑 `sessionStorage` 作为折中方案。
