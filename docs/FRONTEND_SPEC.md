# SafeEmail Web 客户端 — 技术规格说明书（SPEC）

| 字段     | 内容                              |
| -------- | --------------------------------- |
| 产品名称 | SafeEmail Web 客户端              |
| 文档版本 | v1.0                              |
| 创建日期 | 2026-04-21                        |
| 关联文档 | docs/FRONTEND_PRD.md · docs/PROTOCOL.md · docs/SPEC.md |

---

## 1 技术选型

| 层面       | 选型                           | 说明                        |
| ---------- | ------------------------------ | --------------------------- |
| 框架       | React 18 + TypeScript          | 组件化、类型安全             |
| 构建工具   | Vite                           | 极速 HMR，开箱即用           |
| UI 组件库  | Ant Design 5                   | 成熟的企业级组件，邮箱适配好 |
| 路由       | React Router v6                | SPA 路由管理                |
| 状态管理   | Zustand                        | 轻量、TypeScript 友好       |
| 通信       | 原生 WebSocket                 | 与网关直连，协议透传         |
| 富文本编辑 | React Quill 或 TipTap          | 邮件正文编辑器              |
| 图标       | @ant-design/icons              | 与 Ant Design 配套          |
| WebSocket 网关 | Python asyncio + websockets | 浏览器 ↔ TCP 协议桥接       |

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

### 2.2 数据流

```
用户操作 → React 组件 → Zustand Store → WebSocket Client
    → WS 网关(透传) → TCP 后端 → 响应原路返回
```

### 2.3 WebSocket 网关职责

- 监听 WebSocket 端口（alpha → 3001，beta → 3002）
- 每个 WebSocket 连接对应一条到后端的 TCP + TLS 连接
- **协议透传**：浏览器发来的 JSON 原样转发 TCP 后端，TCP 响应原样回传浏览器
- 消息分界：WebSocket 帧天然有边界，TCP 侧沿用 `\r\n` 分隔
- 连接生命周期：WebSocket 断开时关闭对应 TCP 连接

---

## 3 项目结构

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

## 4 WebSocket 通信层设计

### 4.1 连接管理类

```typescript
class SafeEmailWS {
  private ws: WebSocket;
  private pendingRequests: Map<string, {resolve, reject, timeout}>;
  private reconnectAttempts: number;
  private heartbeatTimer: number;

  connect(url: string): Promise<void>;
  send(action: string, payload: object, token?: string): Promise<Response>;
  disconnect(): void;
  private startHeartbeat(): void;
  private reconnect(): void;
}
```

### 4.2 请求-响应匹配

- 每个请求携带唯一 `request_id`（UUID v4）
- 通过 `pendingRequests` Map 匹配异步响应
- 默认超时 15 秒，超时后自动 reject

### 4.3 自动重连

- 指数退避策略：1s → 2s → 4s → 8s → 16s → 30s（上限）
- WebSocket `onclose` / `onerror` 触发重连
- 重连成功后自动恢复心跳

### 4.4 心跳保活

- 每 30 秒发送 `PING` 消息
- 60 秒无响应则判定断连，触发重连逻辑

### 4.5 消息构造

```typescript
function buildRequest(action: string, payload: object, token?: string) {
  return {
    version: "1.0",
    type: "REQUEST",
    action,
    request_id: crypto.randomUUID(),
    token: token || null,
    payload
  };
}
```

### 4.6 Token 续期拦截

在 `send()` 方法中：
1. 检查 `access_token` 是否临近过期（< 2 分钟）
2. 若是，先执行 `REFRESH` 获取新 Token
3. 再执行原始请求
4. 续期失败则跳转登录页

---

## 5 状态管理设计

### 5.1 authStore（认证状态）

```typescript
interface AuthState {
  accessToken: string | null;       // 内存存储，非 localStorage
  refreshToken: string | null;
  username: string | null;
  domain: string | null;
  userId: string | null;
  isAuthenticated: boolean;

  login(username: string, password: string): Promise<void>;
  register(username: string, password: string): Promise<void>;
  logout(): Promise<void>;
  refresh(): Promise<void>;
  parseTokenExp(): number;          // 从 JWT payload 解析 exp
}
```

### 5.2 mailStore（邮件状态）

```typescript
interface MailState {
  inboxMails: Mail[];
  sentMails: Mail[];
  drafts: Mail[];
  currentMail: MailDetail | null;
  searchResults: SearchResult[];
  currentPage: number;
  totalPages: number;
  loading: boolean;

  fetchInbox(page: number): Promise<void>;
  fetchSent(page: number): Promise<void>;
  fetchDrafts(): Promise<void>;
  readMail(emailId: string): Promise<void>;
  sendMail(to: string[], subject: string, body: string, attachments?: string[]): Promise<void>;
  saveDraft(draft: DraftPayload): Promise<void>;
  recallMail(emailId: string, signature: string): Promise<void>;
  searchMail(query: string): Promise<void>;
  getQuickReplies(emailId: string): Promise<string[]>;
  execAction(emailId: string, actionIndex: number): Promise<void>;
}
```

### 5.3 uiStore（UI 状态）

```typescript
interface UIState {
  sidebarCollapsed: boolean;
  currentRoute: string;
  loading: boolean;
  wsConnected: boolean;
  wsReconnecting: boolean;

  toggleSidebar(): void;
  setLoading(val: boolean): void;
  setWsStatus(connected: boolean, reconnecting?: boolean): void;
}
```

---

## 6 路由设计

| 路由 | 页面组件 | 需登录 | 说明 |
| ---- | -------- | ------ | ---- |
| `/login` | LoginPage | 否 | 登录/注册（Tab 切换） |
| `/register` | LoginPage (tab) | 否 | 注册 |
| `/inbox` | InboxPage | 是 | 收件箱（默认页） |
| `/sent` | SentPage | 是 | 发件箱 |
| `/drafts` | DraftPage | 是 | 草稿箱 |
| `/mail/:id` | MailDetailPage | 是 | 邮件详情 |
| `/compose` | ComposePage | 是 | 写邮件/回复/转发 |
| `/search` | SearchPage | 是 | 搜索结果 |
| `/groups` | GroupPage | 是 | 群组管理 |

### 路由守卫

- 未登录用户访问受保护路由 → 重定向到 `/login`
- 已登录用户访问 `/login` → 重定向到 `/inbox`
- 使用 React Router v6 的 `<Navigate>` 组件实现

---

## 7 核心组件详细设计

### 7.1 WebSocket 网关（server/ws_gateway.py）

```python
# 核心逻辑
async def handle_websocket(websocket):
    # 1. 建立到后端的 TCP+TLS 连接
    ssl_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_cert)
    tcp_reader, tcp_writer = await asyncio.open_connection(
        backend_host, backend_port, ssl=ssl_ctx
    )
    # 2. 双向透传
    await asyncio.gather(
        ws_to_tcp(websocket, tcp_writer),
        tcp_to_ws(tcp_reader, websocket),
    )

async def ws_to_tcp(ws, tcp_writer):
    async for message in ws:
        tcp_writer.write(message.encode() + b'\r\n')
        await tcp_writer.drain()

async def tcp_to_ws(tcp_reader, ws):
    while True:
        data = await tcp_reader.readline()  # \r\n 分隔
        if not data:
            break
        await ws.send(data.decode().strip())
```

**配置**：
- alpha 网关：ws://127.0.0.1:3001 → TCP 127.0.0.1:8001
- beta 网关：ws://127.0.0.1:3002 → TCP 127.0.0.1:8002

### 7.2 认证模块组件

#### LoginForm
- 用户名校验：≥ 3 字符
- 密码校验：≥ 8 位，包含大写 + 小写 + 数字
- 登录失败处理：401 错误提示、429 限流倒计时、captcha 验证码弹窗
- 使用 Ant Design `Form` + `Input` + `Button`

#### RegisterForm
- 字段：用户名、密码、确认密码
- 确认密码一致性校验
- 成功后跳转登录页，显示 "注册成功，请登录"

#### CaptchaModal
- 当后端返回 `captcha_required: true` 时弹出
- 显示 `captcha_question`（数学题）
- 用户输入答案后附加 `captcha_answer` 字段重新提交

### 7.3 邮件列表组件

#### MailList
- 通用列表组件，接收 `Mail[]` 数据
- 支持分页器（默认 20 条/页）
- 支持骨架屏加载态
- 支持空状态展示

#### MailListItem
- 显示：发件人/收件人、主题、时间、已读/未读状态
- 未读邮件加粗，已读灰色
- 垃圾邮件 `is_spam=true` 显示 ⚠️ 标签 + 淡黄/淡红背景
- 已撤回邮件显示"已撤回"灰色斜体标签
- 点击跳转邮件详情

### 7.4 邮件详情组件

#### MailViewer
- 邮件头：From / To / Time
- 正文：通过 iframe sandbox 或 DOMPurify 安全渲染 HTML
- 垃圾邮件警告：顶部红色警告条

#### AttachmentBar
- 附件列表：文件名、大小、类型图标
- 下载：`DOWNLOAD_ATTACH` → Base64 解码 → 浏览器下载
- 图片预览：`image/*` 类型点击弹出大图预览

#### ActionButtons
- 从邮件 `actions` 字段动态渲染按钮
- `schedule` → 直接执行，Toast 提示
- `confirm/reject` → 二次确认弹窗
- `safe_link` → 安全检查，安全则新窗口打开，不安全则警告拦截
- `summary` → 复制到剪贴板

#### QuickReplyBar
- 调用 `QUICK_REPLY` 获取 3 条回复建议
- 点击建议 → 跳转写邮件页预填内容

#### RecallButton
- 仅当前用户是发件人且在 5 分钟窗口内显示
- 显示倒计时（如"还剩 3:24"）
- 点击弹出确认对话框
- 使用后端预生成的 `recall_signature`（不在前端计算 HMAC）

### 7.5 写邮件组件

#### ComposeForm
- 收件人：Tag 输入，支持多地址（逗号/回车分隔），支持 `user` 或 `user@domain`
- 群组选择：弹窗列出群组，选择后展开为成员地址
- 主题输入
- 富文本编辑器：加粗/斜体/链接/图片
- 附件上传：拖拽或点击，Base64 编码，限制 ≤ 15MB
- 草稿自动保存：每 30 秒 + 手动按钮
- 回复模式：自动填充收件人、主题（`Re: 原主题`）、引用原文
- 草稿模式：预填草稿内容，传递 `draft_id`

---

## 8 安全设计

### 8.1 Token 安全

- `access_token` 和 `refresh_token` 仅存储在 JavaScript 内存变量（Zustand store）
- **不写入** localStorage / sessionStorage / cookie
- 页面刷新后 Token 丢失，用户需重新登录（安全优先策略）

### 8.2 XSS 防护

- 邮件正文渲染方案（二选一）：
  - iframe sandbox：`<iframe sandbox="allow-same-origin" srcdoc={sanitizedHtml} />`
  - DOMPurify 二次清洗：`dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(body) }}`
- 用户输入（收件人、主题）统一转义

### 8.3 HMAC 签名

- **撤回签名**：由后端在 `LIST_SENT` / `READ_MAIL` 响应中预生成 `recall_signature` 字段下发，前端直接回传，不在前端计算
- **快捷操作签名**：由后端在邮件 `actions` 字段中预生成，前端直接使用

### 8.4 WebSocket 安全

- 网关层仅做透传，不解析/修改消息内容
- 所有业务鉴权由后端 TCP 服务处理
- 前端 Token 过期自动续期，续期失败跳转登录

---

## 9 环境配置

### 9.1 前端环境变量

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

### 9.2 后端网关配置

```yaml
# config/alpha.yaml 新增
ws_gateway:
  host: "127.0.0.1"
  port: 3001

# config/beta.yaml 新增
ws_gateway:
  host: "127.0.0.1"
  port: 3002
```

### 9.3 启动命令

```bash
# WebSocket 网关
python server/ws_gateway.py config/alpha.yaml   # alpha 网关 :3001
python server/ws_gateway.py config/beta.yaml    # beta 网关 :3002

# 前端开发服务器
cd web && npx vite --mode alpha --port 5173     # alpha 前端
cd web && npx vite --mode beta --port 5174      # beta 前端

# 一键启动（后端 + 网关 + 前端）
python scripts/start_all.py
```

---

## 10 UI/UX 规范

### 10.1 视觉风格

- 主色调：蓝色系 `#1677ff`
- 侧边栏：深色 `#001529`
- 字体栈：`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- 最小宽度：1024px（桌面端优先）
- 侧边栏可折叠

### 10.2 交互规范

| 场景     | 交互                                      |
| -------- | ----------------------------------------- |
| 操作成功 | 右上角 Toast 通知（绿色，3 秒消失）        |
| 操作失败 | 右上角 Toast 通知（红色，5 秒消失）        |
| 危险操作 | Modal 二次确认（撤回、删除）               |
| 加载中   | 按钮 Loading 旋转，列表骨架屏              |
| 空状态   | 居中图标 + 文案（如"收件箱是空的"）        |
| 网络断开 | 顶部全宽黄色警告条："网络连接已断开，正在重连..." |

### 10.3 域名标识

- 登录页 / 侧边栏顶部展示当前域名（如 `alpha.local`）
- 可选主题色区分：alpha → 蓝色，beta → 绿色

---

## 11 非功能性需求

| 项目           | 要求                                    |
| -------------- | --------------------------------------- |
| 首屏加载       | < 2 秒（Vite 构建优化）                 |
| WebSocket 重连 | 断线自动重连，指数退避最大 30s           |
| Token 安全     | 仅存内存，不写入 localStorage / cookie   |
| XSS 防护       | iframe sandbox 或 DOMPurify 二次清洗     |
| 浏览器兼容     | Chrome 90+, Firefox 88+, Edge 90+, Safari 14+ |
| 国际化         | 初始版本仅支持中文                       |

---

## 12 依赖清单

### 前端依赖

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.x",
    "antd": "^5.x",
    "@ant-design/icons": "^5.x",
    "zustand": "^4.x",
    "react-quill": "^2.x",
    "dompurify": "^3.x",
    "uuid": "^9.x"
  },
  "devDependencies": {
    "typescript": "^5.x",
    "vite": "^5.x",
    "@types/react": "^18.x",
    "@types/react-dom": "^18.x",
    "@vitejs/plugin-react": "^4.x"
  }
}
```

### 网关依赖（Python）

```
websockets>=12.0
```
