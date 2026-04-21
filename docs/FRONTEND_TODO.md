# SafeEmail Web 客户端 — 开发待办事项（TODO）

> 基于 FRONTEND_PRD v1.0 与 FRONTEND_SPEC v1.0，按里程碑分阶段推进。
> 状态标记：⬜ 待开始 | 🔲 进行中 | ✅ 完成 | ❌ 取消

---

## F1 — 基础框架与认证（预计 2 天）

### 项目初始化
- ✅ 使用 Vite 创建 React + TypeScript 项目（`web/` 目录）
- ✅ 安装核心依赖（antd, @ant-design/icons, react-router-dom, zustand）
- ✅ 配置 `vite.config.ts`（路径别名、代理）
- ✅ 配置 `tsconfig.json`（strict 模式、路径映射）
- ✅ 创建环境变量文件 `web/.env.alpha` 和 `web/.env.beta`
- ✅ 实现 `src/config.ts`（读取 VITE_WS_URL / VITE_DOMAIN / VITE_APP_TITLE）

### WebSocket 网关
- ✅ 实现 `server/ws_gateway.py`（Python asyncio + websockets）
  - WebSocket 监听（alpha:3001 / beta:3002）
  - 每连接对应一条 TCP+TLS 后端连接
  - 双向透传（WS ↔ TCP，`\r\n` 分隔）
  - 连接生命周期管理（WS 断开时关闭 TCP）
- ✅ 后端配置新增 `ws_gateway` 段（config/alpha.yaml, config/beta.yaml）
- ⬜ 验证：浏览器通过 WS 网关发送 PING，后端返回 PONG（待后端联调）

### WebSocket 通信层
- ✅ 实现 `src/api/ws.ts`（SafeEmailWS 类）
  - 连接/断开管理
  - request_id 请求-响应匹配（pendingRequests Map）
  - 超时机制（默认 15 秒）
  - 自动重连（指数退避：1s → 2s → 4s → 8s → 30s 上限）
  - 心跳保活（每 30 秒 PING，60 秒无响应触发重连）
- ✅ 实现 `src/api/protocol.ts`（消息构造函数 buildRequest）
- ✅ 实现 `src/api/client.ts`（高层 API 封装：login/register/logout/refresh 等）
- ⬜ 实现 `src/hooks/useWebSocket.ts`（WebSocket 连接 React Hook）（功能已集成到 authStore.init）

### 类型定义
- ✅ 实现 `src/types/protocol.ts`（请求/响应消息类型）
- ✅ 实现 `src/types/auth.ts`（认证相关类型）
- ✅ 实现 `src/types/mail.ts`（邮件/附件/群组相关类型）

### 状态管理
- ✅ 实现 `src/stores/authStore.ts`（token/用户信息/登录/注册/登出/续期）
- ✅ 实现 `src/stores/uiStore.ts`（侧边栏折叠/加载态/WS 连接状态）
- ✅ 实现 `src/stores/mailStore.ts`（邮件列表/当前邮件/搜索结果）

### 路由与守卫
- ✅ 实现 `src/App.tsx`（React Router v6 路由配置）
- ✅ 实现路由守卫（未登录 → `/login`，已登录访问 `/login` → `/inbox`）
- ✅ 根路由 `/` 重定向到 `/inbox`

### 认证页面（P1-P4）
- ✅ 实现 `src/components/Auth/LoginForm.tsx`
  - 用户名校验（≥ 3 字符）
  - 密码校验（≥ 8 位，大写+小写+数字）
  - 登录成功 → 存 Token（内存）→ 跳转收件箱
  - 登录失败（401）→ 错误提示
  - 限流（429）→ 按钮禁用 + 倒计时
- ✅ 实现 `src/components/Auth/RegisterForm.tsx`
  - 确认密码一致性校验
  - 成功后跳转登录页，提示"注册成功，请登录"
- ✅ 实现 `src/components/Auth/CaptchaModal.tsx`
  - 登录失败触发 `captcha_required` 时弹出
  - 显示数学题，用户作答后重新提交
- ✅ 实现 `src/pages/LoginPage.tsx`（Tab 切换登录/注册）
- ✅ 实现 `src/utils/validators.ts`（密码/用户名前端预校验规则）

### Token 自动续期（P3）
- ✅ 实现 `src/hooks/useAuth.ts`
  - 解析 JWT payload 获取 `exp`
  - 过期前 2 分钟自动发送 `REFRESH`
  - 续期失败跳转登录页

### 登出（P4）
- ✅ 顶栏右上角登出按钮（集成于 authStore.logout）
- ✅ 发送 `LOGOUT`，清除内存 Token，跳转登录页

---

## F2 — 邮件核心功能（预计 2 天）

### 整体布局
- ✅ 实现 `src/components/Layout/AppLayout.tsx`（侧边栏 + 顶栏 + 内容区）
- ✅ 实现 `src/components/Layout/Sidebar.tsx`（导航：收件箱/发件箱/草稿箱/群组）
  - 展示当前域名标识
  - 可折叠
- ✅ 实现 `src/components/Layout/Header.tsx`（搜索框 + 用户信息 + 登出按钮 + 网络断开警告条）

### 通用邮件组件
- ✅ 实现 `src/components/Mail/MailList.tsx`（邮件列表 + 分页器 + 骨架屏 + 空状态）
- ✅ 实现 `src/components/Mail/MailListItem.tsx`（发件人/收件人、主题、时间、已读/未读、垃圾标记、撤回样式）
- ✅ 实现 `src/components/Common/EmptyState.tsx`（空状态提示组件）
- ✅ 实现 `src/components/Common/SpamBadge.tsx`（垃圾邮件 ⚠️ 标签）

### 收件箱（P5）
- ✅ 实现 `src/pages/InboxPage.tsx`
  - 调用 `LIST_INBOX` 获取邮件列表
  - 分页（默认 20 条/页）
  - 未读加粗、已读灰色
  - 垃圾邮件标记（⚠️ + 淡黄背景）
  - 点击邮件行 → 跳转 `/mail/:id`

### 发件箱（P6）
- ✅ 实现 `src/pages/SentPage.tsx`
  - 调用 `LIST_SENT` 获取发送记录
  - 已撤回邮件显示“已撤回”标签
  - 5 分钟窗口内的已发送邮件显示撤回按钮（F3 实现）

### 草稿箱（P7）
- ✅ 实现 `src/pages/DraftPage.tsx`
  - 调用 `LIST_DRAFTS` 获取草稿列表
  - 点击草稿 → 跳转写邮件页（预填内容，携带 `draft_id`）

### 邮件详情（P8）
- ✅ 实现 `src/components/Mail/MailViewer.tsx`
  - 邮件头（From / To / Time）
  - HTML 正文安全渲染（DOMPurify）
  - 垃圾邮件顶部红色警告条
- ✅ 实现 `src/pages/MailDetailPage.tsx`
  - 调用 `READ_MAIL` 获取邮件详情 + 标记已读
  - 返回按钮
  - 集成 MailViewer / 附件展示 / 回复 / 转发按钮
  - AttachmentBar / ActionButtons / QuickReplyBar / RecallButton 待 F3 集成

### 写邮件（P9）
- ✅ 实现 `src/components/Mail/ComposeForm.tsx`
  - 收件人 Tag 输入（多地址，逗号/回车分隔）
  - 群组选择按钮（F4 实现）
  - 主题输入
  - 富文本编辑器（TipTap）
  - 附件上传区域（F3 实现 AttachmentUploader）
  - 保存草稿按钮 + 发送按钮
- ✅ 实现 `src/pages/ComposePage.tsx`
  - 普通模式：空白写邮件
  - 回复模式（`?reply=<emailId>`）：预填收件人、主题 `Re:`、引用原文
  - 转发模式（`?forward=<emailId>`）：预填主题 `Fwd:`、原文
  - 草稿模式（`?draft=<draftId>`）：预填草稿内容
  - 发送成功 → Toast + 跳转发件箱
- ✅ 实现草稿自动保存（每 30 秒调用 `SAVE_DRAFT`）

### 邮件操作 Hook
- ✅ 邮件操作已集成到 `mailStore`，不再单独抽取 Hook

---

## F3 — 高级功能（预计 1.5 天）

### 邮件搜索（P11）
- ✅ 实现 `src/pages/SearchPage.tsx`
  - 顶栏搜索框输入 → 回车 → 发送 `SEARCH_MAIL`
  - 搜索结果列表（邮件 ID、发件人、主题、时间、匹配类型、相关性评分）
  - 点击结果 → 跳转邮件详情

### 邮件撤回（P10）
- ✅ 实现 `src/components/Common/RecallButton.tsx`
  - 5 分钟窗口倒计时显示（如“还剩 3:24”）
  - 点击 → 二次确认对话框
  - 使用后端下发的 `recall_signature`（不在前端计算 HMAC）
  - 发送 `RECALL_MAIL`
  - 成功显示“已撤回”，`already_read=true` 时额外提示

### 附件上传与下载（P12-P13）
- ✅ 实现 `src/components/Mail/AttachmentBar.tsx`
  - 写邮件模式：拖拽/点击上传，文件 → Base64 → `UPLOAD_ATTACH`
  - 上传进度条（估算）、文件名 + 大小 + 删除按钮
  - 单文件限制 ≤ 15MB
  - 阅读模式：附件列表、类型图标
  - 下载（`DOWNLOAD_ATTACH` → Base64 解码 → 浏览器下载）
  - 图片预览（`image/*` 点击弹出大图）

### 快速回复建议（P8 补充）
- ✅ 实现 `src/components/Mail/QuickReplyBar.tsx`
  - 调用 `QUICK_REPLY` 获取 3 条回复建议
  - 点击建议 → 跳转写邮件页并预填

### 快捷操作按钮（P8 补充）
- ✅ 实现 `src/components/Mail/ActionButtons.tsx`
  - 从邮件 `actions` 字段动态渲染
  - `schedule` → 直接执行 `EXEC_ACTION`，Toast 提示“已添加日程”
  - `confirm/reject` → 二次确认弹窗后执行
  - `safe_link` → 安全则新窗口打开，不安全则警告拦截
  - `summary` → 复制到剪贴板

### 工具函数
- ✅ 实现 `src/utils/format.ts`（日期格式化、文件大小格式化）
- ✅ 实现 `src/utils/hmac.ts`（预留 HMAC 工具，实际使用后端预生成签名）

---

## F4 — 群组与安全提示（预计 1 天）

### 群组管理（P14）
- ✅ 实现 `src/components/Group/GroupList.tsx`
  - 调用 `LIST_GROUPS` 获取群组列表
  - 显示群组名称、成员数量、成员列表（展开/收起）
- ✅ 实现 `src/components/Group/GroupForm.tsx`
  - 创建群组弹窗：群组名 + 成员地址（多行输入）
  - 调用 `CREATE_GROUP`
- ✅ 实现 `src/pages/GroupPage.tsx`（群组管理页面）
- ✅ 写邮件时群组选择器集成（GroupSelector）

### 垃圾邮件提示（P15-P16）
- ✅ 收件箱垃圾邮件标识（⚠️ 图标 + 背景色）— 已在 F2 MailListItem 实现
- ✅ 邮件详情顶部红色警告条 — 已在 F2 MailViewer 实现
- ✅ 发送时 `spam_warning` 响应弹窗（显示 `spam_reasons`）

### 限流提示（P17）
- ✅ 登录限流提示：“登录尝试过于频繁，请等待 X 分钟后再试” — 已在 F1 LoginForm 实现
- ✅ 发送限流提示：“发送频率过高，请稍后再试” — 已在 ComposeForm 实现

### 验证码（P18）
- ✅ 登录失败 3 次后弹出验证码（CaptchaModal 已在 F1 实现并集成）

---

## F5 — 打磨与启动脚本（预计 0.5 天）

### 双域名验证
- ⬜ alpha 前端（:5173）通过 WS 网关（:3001）连接 alpha 后端（:8001）端到端验证
- ⬜ beta 前端（:5174）通过 WS 网关（:3002）连接 beta 后端（:8002）端到端验证
- ⬜ 两个域名实例数据完全隔离验证

### 一键启动脚本
- ✅ 编写 `scripts/start_all.py`（启动后端 + WS 网关 + 前端 dev server）
- ⬜ 验证一键启动正常运行

### 交互细节打磨
- ✅ 网络断开时顶部黄色警告条 — 已在 F2 Header 实现
- ✅ 所有操作的 Loading 态（按钮旋转、列表骨架屏）
- ✅ 所有错误的 Toast 提示（红色）
- ✅ 所有成功的 Toast 提示（绿色）
- ✅ 空状态提示（收件箱/发件箱/草稿箱/搜索结果为空）

### 整体冒烟测试
- ⬜ 注册 → 登录 → 写邮件 → 发送 → 收件箱查看 → 阅读 → 回复 全流程
- ⬜ 附件上传/下载/预览
- ⬜ 邮件撤回（窗口内 + 超时）
- ⬜ 搜索功能
- ⬜ 群组创建 + 群发
- ⬜ Token 自动续期
- ⬜ 限流/验证码触发

---

## 依赖关系

```
F1 (基础框架+认证) → F2 (邮件核心) → F3 (高级功能)
                                          ↓
                                    F4 (群组+安全提示)
                                          ↓
                                    F5 (打磨+启动脚本)
```

---

## 风险与注意事项

1. **HMAC 签名安全**：前端不持有 `jwt_secret`，撤回签名由后端预生成随邮件下发，前端仅回传
2. **大附件传输**：15MB Base64 编码后约 20MB，WebSocket 单帧可能过大，需关注浏览器内存
3. **WebSocket 网关单点**：单 asyncio 进程，预计支持 50+ 并发连接，满足开发演示需求
4. **富文本安全**：用户输入 HTML 发送前无需前端清洗（后端已处理），但显示其他用户邮件时需 DOMPurify / iframe sandbox
5. **Token 持久化**：刷新页面丢失 Token（安全设计），用户需重新登录
6. **CORS**：WebSocket 天然跨域，但网关需正确处理 Origin 头校验
