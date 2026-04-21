# SafeEmail 通信协议说明

## 1 传输层

| 项目 | 说明 |
|------|------|
| 传输协议 | TCP + TLS 1.3 |
| 消息边界 | JSON + `\r\n` 分隔符 |
| 编码 | UTF-8 |
| 最大消息 | 15MB（含 Base64 附件） |

## 2 消息格式

### 请求消息

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

### 响应消息

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

### S2S 中继消息

```json
{
    "version": "1.0",
    "type": "S2S_REQUEST",
    "action": "S2S_DELIVER",
    "server_id": "alpha.local",
    "signature": "<HMAC-SHA256>",
    "payload": { "email": { ... } }
}
```

## 3 状态码

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 200 | 成功 | 正常操作完成 |
| 201 | 创建成功 | 注册、附件上传 |
| 400 | 请求错误 | 参数缺失/格式错误 |
| 401 | 未认证 | Token 无效/过期 |
| 403 | 权限不足 | 无权操作（非发件人撤回） |
| 404 | 不存在 | 邮件/附件/用户不存在 |
| 409 | 冲突 | 用户名已存在 |
| 429 | 频率限制 | 发送/登录超过阈值 |
| 500 | 服务器错误 | 内部异常 |

## 4 Action 列表

### 认证类

| Action | 需要 Token | 说明 | Payload |
|--------|-----------|------|---------|
| `REGISTER` | 否 | 注册 | `{username, password}` |
| `LOGIN` | 否 | 登录 | `{username, password}` |
| `LOGOUT` | 是 | 登出 | `{}` |
| `REFRESH` | 否 | 续期 | `{refresh_token}` |

### 邮件类

| Action | 需要 Token | 说明 | Payload |
|--------|-----------|------|---------|
| `SEND_MAIL` | 是 | 发送邮件 | `{to: [], subject, body}` |
| `LIST_INBOX` | 是 | 收件箱 | `{page, page_size}` |
| `READ_MAIL` | 是 | 读取邮件 | `{email_id}` |
| `LIST_SENT` | 是 | 发件箱 | `{page, page_size}` |
| `SAVE_DRAFT` | 是 | 保存草稿 | `{draft_id?, to, subject, body}` |
| `LIST_DRAFTS` | 是 | 草稿列表 | `{}` |
| `RECALL_MAIL` | 是 | 撤回邮件 | `{email_id, signature}` |
| `SEARCH_MAIL` | 是 | 搜索邮件 | `{query, limit?}` |
| `QUICK_REPLY` | 是 | 快速回复建议 | `{email_id}` |

### 群组类

| Action | 需要 Token | 说明 | Payload |
|--------|-----------|------|---------|
| `CREATE_GROUP` | 是 | 创建/更新群组 | `{group_name, members}` |
| `LIST_GROUPS` | 是 | 群组列表 | `{}` |

### 附件类

| Action | 需要 Token | 说明 | Payload |
|--------|-----------|------|---------|
| `UPLOAD_ATTACH` | 是 | 上传附件 | `{email_id, filename, content_type, data}` |
| `DOWNLOAD_ATTACH` | 是 | 下载附件 | `{attachment_id}` |

### 快捷操作类

| Action | 需要 Token | 说明 | Payload |
|--------|-----------|------|---------|
| `EXEC_ACTION` | 是 | 执行快捷操作 | `{email_id, action_index, confirm?}` |

### S2S 中继类

| Action | 认证方式 | 说明 |
|--------|---------|------|
| `S2S_DELIVER` | HMAC 签名 | 跨域邮件投递 |
| `S2S_RECALL` | HMAC 签名 | 跨域邮件撤回 |

### 系统类

| Action | 说明 |
|--------|------|
| `PING` | 心跳检测 |

## 5 鉴权流程

### 5.1 注册

```
Client                          Server
  |--- REGISTER (username, pwd) -->|
  |                                |-- 校验用户名(≥3字符)
  |                                |-- 校验密码(≥8位,大小写+数字)
  |                                |-- 检查用户名唯一
  |                                |-- bcrypt(pwd, cost=12) 存储
  |<--- 201 Created (user_id) -----|
```

### 5.2 登录

```
Client                          Server
  |--- LOGIN (username, pwd) ----->|
  |                                |-- 检查 IP 限流 (5次/5min)
  |                                |-- 检查账号限流 (10次/10min)
  |                                |-- 验证密码
  |                                |-- 签发 Access Token (30min)
  |                                |-- 签发 Refresh Token (7天)
  |<--- 200 OK (tokens) -----------|
```

### 5.3 认证请求

```
Client                          Server
  |--- Action + Token ------------>|
  |                                |-- 验证 JWT 签名
  |                                |-- 检查过期时间
  |                                |-- 检查黑名单
  |                                |-- 提取 username/domain
  |<--- Response ------------------|
```

### 5.4 Token 续期

```
Client                          Server
  |--- REFRESH (refresh_token) --->|
  |                                |-- 验证 Refresh Token
  |                                |-- 签发新 Access Token
  |<--- 200 OK (new access) -------|
```

## 6 JWT Token 结构

### Access Token

```json
{
    "sub": "<user_id>",
    "username": "<username>",
    "domain": "<domain>",
    "jti": "<uuid4>",
    "iat": "<timestamp>",
    "exp": "<iat + 30min>",
    "type": "access"
}
```

### Refresh Token

```json
{
    "sub": "<user_id>",
    "jti": "<uuid4>",
    "iat": "<timestamp>",
    "exp": "<iat + 7days>",
    "type": "refresh"
}
```

## 7 HMAC 签名机制

### 邮件撤回签名

```
签名内容: "RECALL:{email_id}:{from_user}"
密钥: JWT Secret
算法: HMAC-SHA256
```

### S2S 中继签名

```
签名内容: 邮件投递的完整 payload JSON
密钥: S2S Shared Secret
算法: HMAC-SHA256
```

### 快捷操作签名

```
签名内容: "{email_id}:{action_type}:{data_json}"
密钥: JWT Secret
算法: HMAC-SHA256
```
