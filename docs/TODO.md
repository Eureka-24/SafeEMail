# 智能安全邮箱系统 — 开发待办事项（TODO）

> 基于 PRD v1.0 与 SPEC v1.0，按里程碑分阶段推进。  
> 状态标记：⬜ 待开始 | 🔲 进行中 | ✅ 完成 | ❌ 取消

---

## M1 — 基础框架搭建（预计 3 天）

### 项目初始化
- ✅ 创建项目目录结构（server/client/shared/tests/scripts/config）
- ✅ 编写 `requirements.txt`，安装所有依赖
- ✅ 编写共享模块 `shared/protocol.py`（协议常量、Action 枚举、消息构造工具）
- ✅ 编写共享模块 `shared/crypto.py`（HMAC 工具函数）

### TCP 通信框架
- ✅ 实现服务端 TCP 监听（asyncio.start_server）
- ✅ 实现消息编解码器 `server/protocol/codec.py`（JSON + `\r\n` 分隔，处理粘包/拆包）
- ✅ 实现消息路由分发器 `server/protocol/handler.py`（根据 action 路由到对应处理函数）
- ✅ 实现客户端 TCP 连接管理 `client/connection.py`（异步收发消息）
- ✅ 端到端测试：客户端发送 PING，服务端返回 PONG

### TLS 加密通信
- ✅ 编写 `scripts/generate_certs.py`（自动生成 CA + 服务器证书）
- ✅ 实现 `server/security/tls.py`（TLS 上下文配置）
- ✅ 客户端连接启用 TLS，验证证书链

### 双域名服务器
- ✅ 编写 `config/alpha.yaml` 与 `config/beta.yaml` 配置文件
- ✅ 实现 `server/config.py`（YAML 配置加载）
- ✅ 实现 `server/main.py`（根据配置启动服务器实例）
- ✅ 编写 `scripts/start_servers.py`（一键启动双域名服务器）
- ✅ 验证：两个实例分别监听 8001/8002 端口，互不干扰

---

## M2 — 用户认证体系（预计 2 天）

### 数据库初始化
- ✅ 实现 `server/storage/database.py`（SQLite 连接管理，WAL 模式）
- ✅ 实现 `server/storage/migrations.py`（建表 SQL 执行）
- ✅ 实现 `server/storage/models.py`（数据访问层 CRUD 方法）

### 注册功能 (U-001)
- ✅ 实现密码强度校验（≥8位，大小写+数字）`server/auth/password.py`
- ✅ 实现 bcrypt 密码哈希（cost=12）
- ✅ 实现 REGISTER action 处理（用户名唯一性检查 + 创建用户）
- ✅ 客户端注册命令实现
- ✅ 测试：正常注册、重复用户名、弱密码

### 登录功能 (U-002)
- ✅ 实现 JWT 签发工具 `server/auth/jwt_util.py`（Access + Refresh Token）
- ✅ 实现 LOGIN action 处理（密码验证 + Token 签发）
- ✅ 客户端登录命令实现 + Token 本地保存
- ✅ 测试：正确登录、错误密码、账号锁定

### 会话管理 (U-003)
- ✅ 实现 Token 验证中间件（签名校验 + 过期检查 + 黑名单查询）
- ✅ 实现 REFRESH action（Refresh Token 续期）
- ✅ 客户端自动续期逻辑
- ✅ 测试：Token 过期拒绝、刷新成功、伪造 Token 拒绝

### 登出功能 (U-004)
- ✅ 实现 LOGOUT action（Token 加入黑名单）
- ✅ 实现 Token 黑名单定期清理（过期 Token 自动移除）
- ✅ 测试：登出后 Token 不可复用

### 防暴力破解 (SEC)
- ✅ 实现 `server/auth/rate_limiter.py`
  - IP 级别：5次/5min 锁定 15min
  - 账号级别：10次/10min 锁定 30min
  - 3次失败后触发验证码（简单数学题）
- ✅ 测试：TC-020 暴力登录验证

---

## M3 — 核心邮件功能（预计 3 天）

### 发送邮件 (M-001)
- ✅ 实现 SEND_MAIL action 处理
  - 解析收件人（本域/跨域分拣）
  - 写入邮件表 + 收件人关系表
  - 本域投递：直接写入
- ✅ 客户端写邮件命令
- ✅ 测试：本域发送成功、收件人收到

### 收件箱 (M-002)
- ✅ 实现 LIST_INBOX action（分页、按时间倒序、未读标记）
- ✅ 实现 READ_MAIL action（查看详情 + 标记已读）
- ✅ 客户端收件箱命令
- ✅ 测试：邮件列表正确、已读标记更新

### 发件箱 (M-003)
- ✅ 实现 LIST_SENT action
- ✅ 客户端发件箱命令
- ✅ 测试：发送记录完整

### 草稿箱 (M-004)
- ✅ 实现 SAVE_DRAFT action（保存/更新草稿）
- ✅ 实现 LIST_DRAFTS action
- ✅ 草稿转发送功能
- ✅ 客户端草稿命令
- ✅ 测试：草稿保存/加载/编辑/发送

### 群发 (M-005)
- ✅ SEND_MAIL 支持多收件人
- ✅ 测试：TC-005 三人群发验证

### 群组 (M-006)
- ✅ 实现 CREATE_GROUP action（创建/查询/更新群组）
- ✅ 发送邮件时支持群组展开为成员列表
- ✅ 客户端群组管理命令
- ✅ 测试：群组创建、群发到群组

### 邮件撤回 (M-007)
- ✅ 实现 RECALL_MAIL action
  - 身份校验（仅发送者可撤回）
  - 时间窗口校验（5分钟内）
  - HMAC 签名验证
  - 幂等性处理
  - 已读提示
- ✅ 客户端撤回命令
- ✅ 测试：TC-003 正常撤回、超时拒绝、非本人拒绝、重复撤回

---

## M4 — 跨域中继与隔离（预计 2 天）

### S2S 中继协议
- ✅ 实现 `server/mail/relay.py`
  - 建立服务器间 TLS 连接
  - S2S_DELIVER action 发送与接收
  - HMAC 签名验证
- ✅ 实现跨域邮件投递完整流程
- ✅ 实现跨域撤回（S2S_RECALL）
- ✅ 测试：TC-001 alpha → beta 跨域邮件收发

### 存储隔离验证
- ✅ 实现路径校验逻辑（禁止越权访问对方数据目录）
- ✅ 测试：S-003 路径隔离验证

---

## M5 — 附件与存储优化（预计 2 天）

### 图片附件 (M-009)
- ✅ 实现附件上传（Base64 解码 + 大小校验 ≤ 10MB）
- ✅ 实现 `server/storage/attachment.py`
  - SHA-256 哈希计算
  - 哈希寻址存储（{hash[0:2]}/{hash[2:4]}/{full_hash}）
  - HMAC 完整性签名
- ✅ 实现 DOWNLOAD_ATTACH action（完整性校验 + 返回 Base64）
- ✅ 客户端附件上传/下载命令
- ✅ 测试：TC-004 附件收发完整性

### 附件去重 (A-003)
- ✅ 实现去重逻辑（相同哈希 → ref_count+1，复用存储路径）
- ✅ 实现删除时引用计数递减，归零物理删除
- ✅ 去重不跨域（各域独立）
- ✅ 实现存储空间节省统计接口
- ✅ 测试：TC-030 去重验证、TC-031 删除后引用计数

### 完整性校验
- ✅ 读取附件时验证 HMAC
- ✅ 测试：TC-032 篡改检测

---

## M6 — 安全加固（预计 2 天）

### 发送频率限制
- ✅ 实现 `server/security/rate_limit.py`（滑动窗口算法）
  - 10封/min，60封/hour
  - 单 IP 最大 50 并发连接
  - 单消息 ≤ 15MB
- ✅ 测试：TC-021 高频发送限流

### 钓鱼/垃圾邮件检测
- ✅ 实现 `server/security/spam_detector.py`
  - URL 提取与黑名单比对
  - Homograph 攻击检测
  - 敏感关键词评分引擎
  - 发件人信誉评分
  - 综合评分 → 标记
- ✅ 内置钓鱼域名黑名单与敏感词库
- ✅ 测试：TC-022 钓鱼邮件识别

### XSS 防护
- ✅ 实现 `server/security/sanitizer.py`（HTML 清洗）
- ✅ 测试：TC-023 XSS 注入防护

### 撤回安全核验
- ✅ 测试：TC-024 伪造撤回拒绝

---

## M7 — 智能功能（预计 3 天）

### 关键词提取 (A-001)
- ✅ 实现 `server/intelligence/keyword_extractor.py`
  - jieba 中文分词 + 英文空格分词
  - 停用词过滤
  - TF-IDF 计算 → Top-5 关键词
- ✅ 邮件发送/接收时自动提取关键词并存储
- ✅ 测试：关键词提取质量验证

### 邮件分类 (A-001)
- ✅ 实现 `server/intelligence/classifier.py`
  - 朴素贝叶斯分类器
  - 内置种子训练数据
  - 预定义类别：工作/通知/广告/社交/其他
- ✅ 新邮件自动分类
- ✅ 用户修正反馈接口
- ✅ 测试：分类准确性验证

### 邮件搜索 (A-002)
- ✅ 实现 `server/intelligence/search_engine.py`
  - 倒排索引构建（subject/body/from/to）
  - 编辑距离模糊匹配（阈值 ≤ 2）
  - N-Gram (N=3) 索引
  - 相关性评分排序
- ✅ 实现 SEARCH_MAIL action
- ✅ 邮件写入时同步更新索引
- ✅ 客户端搜索命令
- ✅ 测试：精确搜索、模糊搜索、性能验证

---

## M8 — 快捷操作与快速回复（预计 2 天）

### 快速回复 (M-008)
- ✅ 实现 `server/mail/quick_reply.py`
  - 基于邮件上下文生成 3 条回复建议
  - 自动填充收件人和主题
- ✅ 实现 QUICK_REPLY action
- ✅ 客户端快速回复命令
- ✅ 测试：回复建议合理性

### 快捷操作引擎
- ✅ 实现 `server/intelligence/action_engine.py`
  - 📅 添加日程（解析时间/事件）
  - ✅ 一键确认/拒绝（二次确认 + 签名）
  - 🔗 安全链接跳转（URL 安全检查后跳转）
  - 📋 内容摘要复制（纯文本提取）
- ✅ 实现 EXEC_ACTION action
- ✅ 邮件中嵌入 actions JSON 定义
- ✅ 客户端操作执行命令
- ✅ 安全校验：操作签名验证、沙箱限制
- ✅ 测试：各类快捷操作正确执行

---

## M9 — 测试与验收（预计 3 天）

### 功能联通测试
- ✅ TC-001 跨域邮件收发端到端
- ✅ TC-002 注册登录全流程
- ✅ TC-003 邮件撤回
- ✅ TC-004 附件收发
- ✅ TC-005 群发

### 并发与稳定性测试
- ✅ TC-010 20 客户端并发收发
- ✅ TC-011 高频发送压力测试
- ✅ 编写 `tests/test_concurrent.py`

### 安全测试
- ✅ TC-020 暴力登录防护
- ✅ TC-021 高频发送限流
- ✅ TC-022 钓鱼邮件识别
- ✅ TC-023 XSS 注入防护
- ✅ TC-024 伪造撤回防护

### 附件与存储测试
- ✅ TC-030 附件去重
- ✅ TC-031 去重后删除
- ✅ TC-032 完整性校验

### 审计日志验证
- ✅ 实现 `server/audit/logger.py` 审计日志记录器
- ✅ 集成审计日志到认证/邮件/安全服务
- ✅ 验证所有关键操作（登录/发送/撤回/限流触发）均有日志记录
- ✅ 日志格式符合规范（JSON，含时间戳/级别/模块/请求ID）

---

## M10 — 文档与收尾（预计 1 天）

### 文档
- ✅ 编写启动指南（README.md 完整改写）
- ✅ 编写协议说明文档（docs/PROTOCOL.md — Action 列表、鉴权流程、消息格式、HMAC 签名）
- ✅ 编写威胁模型说明文档（docs/THREAT_MODEL.md — 12 项威胁分析 + POC）

### 交付物检查
- ✅ 确认交付物清单完整（服务端/客户端/脚本/配置/测试/文档）
- ✅ 代码整理与注释完善
- ✅ 最终集成测试通过（130 个测试全部通过）

---

## 依赖关系

```
M1 (基础框架) → M2 (认证) → M3 (邮件) → M4 (跨域中继)
                    ↓                          ↓
               M6 (安全加固)              M5 (附件存储)
                    ↓                          ↓
               M7 (智能功能) ──────────→ M8 (快捷操作)
                                              ↓
                                        M9 (测试验收)
                                              ↓
                                        M10 (文档交付)
```

---

## 风险与注意事项

1. **SQLite 并发写入**：使用 WAL 模式 + 写操作队列序列化，避免锁冲突
2. **大附件 Base64 传输**：15MB 限制 → Base64 后约 20MB，注意内存占用
3. **自签名证书**：客户端需配置信任 CA，或开发模式跳过验证
4. **jieba 首次加载**：首次分词有加载延迟，建议服务启动时预热
5. **跨域中继可靠性**：对端不可达时需队列暂存，重试机制
