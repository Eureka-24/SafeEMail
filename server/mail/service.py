"""
邮件服务 - 邮件收发/撤回/草稿/群发
"""
import uuid
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from shared.protocol import Action, StatusCode, build_response
from shared.crypto import compute_hmac
from server.storage.database import Database
from server.config import ServerConfig
from server.security.rate_limit import SendRateLimiter
from server.security.spam_detector import SpamDetector
from server.security.sanitizer import HTMLSanitizer
from server.intelligence.keyword_extractor import KeywordExtractor
from server.intelligence.classifier import DeepSeekClassifier
from server.intelligence.search_engine import SearchEngine
from server.mail.quick_reply import QuickReplyGenerator
from server.intelligence.action_engine import ActionEngine
from server.audit.logger import AuditLogger

logger = logging.getLogger(__name__)


class MailService:
    """邮件服务"""

    def __init__(self, db: Database, config: ServerConfig):
        self.db = db
        self.config = config
        self.domain = config.domain
        self.relay_client = None  # 由 main.py 注入
        self.send_rate_limiter = SendRateLimiter(db, config.security)
        self.spam_detector = SpamDetector()
        self.sanitizer = HTMLSanitizer()
        self.keyword_extractor = KeywordExtractor(top_n=config.intelligence.keyword_top_n)
        self.classifier = DeepSeekClassifier(categories=config.intelligence.categories)
        self.search_engine = SearchEngine(db, max_distance=config.intelligence.fuzzy_max_distance,
                                          ngram_size=config.intelligence.ngram_size)
        self.quick_reply = QuickReplyGenerator()
        self.action_engine = ActionEngine(hmac_secret=config.security.jwt_secret)
        self.audit = AuditLogger(db)

    async def handle_send_mail(self, msg: dict) -> dict:
        """处理发送邮件请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        token_payload = msg.get("_token_payload", {})

        sender_username = token_payload.get("username", "")
        sender_domain = token_payload.get("domain", self.domain)
        from_user = f"{sender_username}@{sender_domain}"

        # 解析收件人
        to_users = payload.get("to", [])
        if isinstance(to_users, str):
            to_users = [to_users]
        
        if not to_users:
            return build_response(request_id, StatusCode.BAD_REQUEST, "收件人不能为空")

        subject = payload.get("subject", "")
        body = payload.get("body", "")

        # 检查发送频率限制
        allowed, rate_msg = await self.send_rate_limiter.check_send_rate(from_user)
        if not allowed:
            await self.audit.log_rate_limit(from_user, "SEND_MAIL")
            return build_response(request_id, StatusCode.TOO_MANY_REQUESTS, rate_msg)

        # HTML 清洗（XSS 防护）
        body = self.sanitizer.sanitize(body)

        # 钓鱼/垃圾邮件检测
        spam_result = self.spam_detector.detect(subject, body, from_user)

        # 创建邮件
        email_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        await self.db.execute(
            """INSERT INTO emails (email_id, from_user, to_users, subject, body, status, created_at, sent_at, is_spam, spam_score)
               VALUES (?, ?, ?, ?, ?, 'SENT', ?, ?, ?, ?)""",
            (email_id, from_user, json.dumps(to_users), subject, body, now, now,
             1 if spam_result.is_spam else 0, spam_result.spam_score)
        )

        # 分拣：本域/跨域
        local_recipients = []
        remote_recipients = []

        for recipient in to_users:
            if "@" in recipient:
                _, domain = recipient.split("@", 1)
                if domain == self.domain:
                    local_recipients.append(recipient)
                else:
                    remote_recipients.append(recipient)
            else:
                # 未指定域名，默认本域
                local_recipients.append(f"{recipient}@{self.domain}")

        # 本域投递：写入收件人关系表
        for recipient in local_recipients:
            await self.db.execute(
                "INSERT INTO email_recipients (email_id, recipient, is_read, is_recalled) VALUES (?, ?, 0, 0)",
                (email_id, recipient)
            )

        # 跨域收件人也记录，并触发中继投递
        for recipient in remote_recipients:
            await self.db.execute(
                "INSERT INTO email_recipients (email_id, recipient, is_read, is_recalled) VALUES (?, ?, 0, 0)",
                (email_id, recipient)
            )

        await self.db.commit()

        # 记录发送频率
        await self.send_rate_limiter.record_send(from_user)

        # 智能引擎：提取关键词、分类、更新搜索索引
        full_text = f"{subject} {body}"
        keywords = self.keyword_extractor.extract_keywords_simple(full_text)
        category, _ = await self.classifier.classify(full_text, self.keyword_extractor.tokenize)
        
        # 生成快捷操作定义
        actions = self.action_engine.build_actions(body, email_id)
        actions_json = json.dumps(actions, ensure_ascii=False) if actions else None

        # 更新邮件记录中的关键词、分类和快捷操作
        await self.db.execute(
            "UPDATE emails SET keywords = ?, category = ?, actions = ? WHERE email_id = ?",
            (json.dumps(keywords, ensure_ascii=False), category, actions_json, email_id)
        )
        await self.db.commit()
        
        # 更新搜索索引
        await self.search_engine.index_email(
            email_id, subject, body, from_user, json.dumps(to_users)
        )

        # 跨域投递
        if remote_recipients and self.relay_client:
            # 按域名分组
            domain_groups = {}
            for recipient in remote_recipients:
                _, domain = recipient.split("@", 1)
                domain_groups.setdefault(domain, []).append(recipient)
            
            email_data = {
                "email_id": email_id,
                "from_user": from_user,
                "to_users": to_users,
                "subject": subject,
                "body": body,
                "sent_at": now,
                "created_at": now
            }
            
            for domain, recipients in domain_groups.items():
                asyncio.create_task(
                    self.relay_client.deliver_mail(domain, email_data)
                )

        logger.info(f"邮件发送成功: {from_user} -> {to_users}, email_id={email_id}")
        await self.audit.log_send_mail(from_user, to_users, email_id, is_spam=spam_result.is_spam)
        response_data = {
            "email_id": email_id,
            "from": from_user,
            "to": to_users,
            "remote_recipients": remote_recipients
        }
        if spam_result.is_spam:
            response_data["spam_warning"] = True
            response_data["spam_score"] = spam_result.spam_score
            response_data["spam_reasons"] = spam_result.reasons
        return build_response(request_id, StatusCode.OK, "发送成功", response_data)

    async def handle_list_inbox(self, msg: dict) -> dict:
        """处理收件箱列表请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        token_payload = msg.get("_token_payload", {})

        username = token_payload.get("username", "")
        domain = token_payload.get("domain", self.domain)
        recipient = f"{username}@{domain}"

        page = payload.get("page", 1)
        page_size = payload.get("page_size", 20)
        offset = (page - 1) * page_size

        # 查询收件箱
        rows = await self.db.fetchall(
            """SELECT e.email_id, e.from_user, e.subject, e.created_at, e.sent_at,
                      er.is_read, er.is_recalled
               FROM email_recipients er
               JOIN emails e ON er.email_id = e.email_id
               WHERE er.recipient = ? AND er.is_recalled = 0 AND e.status = 'SENT'
               ORDER BY e.sent_at DESC
               LIMIT ? OFFSET ?""",
            (recipient, page_size, offset)
        )

        emails = [dict(row) for row in rows] if rows else []

        # 统计总数
        count_row = await self.db.fetchone(
            """SELECT COUNT(*) as total FROM email_recipients er
               JOIN emails e ON er.email_id = e.email_id
               WHERE er.recipient = ? AND er.is_recalled = 0 AND e.status = 'SENT'""",
            (recipient,)
        )
        total = count_row["total"] if count_row else 0

        return build_response(request_id, StatusCode.OK, "收件箱", {
            "emails": emails,
            "total": total,
            "page": page,
            "page_size": page_size
        })

    async def handle_read_mail(self, msg: dict) -> dict:
        """处理阅读邮件请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        token_payload = msg.get("_token_payload", {})

        email_id = payload.get("email_id", "")
        username = token_payload.get("username", "")
        domain = token_payload.get("domain", self.domain)
        recipient = f"{username}@{domain}"

        if not email_id:
            return build_response(request_id, StatusCode.BAD_REQUEST, "缺少 email_id")

        # 查询邮件详情
        email = await self.db.fetchone(
            "SELECT * FROM emails WHERE email_id = ?", (email_id,)
        )
        if not email:
            return build_response(request_id, StatusCode.NOT_FOUND, "邮件不存在")

        # 检查权限（收件人或发件人）
        email_dict = dict(email)
        to_users = json.loads(email_dict["to_users"])
        if recipient not in to_users and email_dict["from_user"] != recipient:
            return build_response(request_id, StatusCode.FORBIDDEN, "无权查看此邮件")

        # 标记已读
        await self.db.execute(
            "UPDATE email_recipients SET is_read = 1 WHERE email_id = ? AND recipient = ?",
            (email_id, recipient)
        )
        await self.db.commit()

        return build_response(request_id, StatusCode.OK, "邮件详情", {
            "email_id": email_dict["email_id"],
            "from": email_dict["from_user"],
            "to": to_users,
            "subject": email_dict["subject"],
            "body": email_dict["body"],
            "sent_at": email_dict["sent_at"],
            "status": email_dict["status"]
        })

    async def handle_list_sent(self, msg: dict) -> dict:
        """处理发件箱列表请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        token_payload = msg.get("_token_payload", {})

        username = token_payload.get("username", "")
        domain = token_payload.get("domain", self.domain)
        from_user = f"{username}@{domain}"

        page = payload.get("page", 1)
        page_size = payload.get("page_size", 20)
        offset = (page - 1) * page_size

        rows = await self.db.fetchall(
            """SELECT email_id, to_users, subject, sent_at, status
               FROM emails
               WHERE from_user = ? AND status IN ('SENT', 'RECALLED')
               ORDER BY sent_at DESC
               LIMIT ? OFFSET ?""",
            (from_user, page_size, offset)
        )

        emails = []
        for row in (rows or []):
            d = dict(row)
            d["to"] = json.loads(d.pop("to_users"))
            emails.append(d)

        return build_response(request_id, StatusCode.OK, "发件箱", {
            "emails": emails,
            "page": page,
            "page_size": page_size
        })

    async def handle_save_draft(self, msg: dict) -> dict:
        """处理保存草稿请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        token_payload = msg.get("_token_payload", {})

        username = token_payload.get("username", "")
        domain = token_payload.get("domain", self.domain)
        from_user = f"{username}@{domain}"

        draft_id = payload.get("draft_id", "")  # 更新已有草稿
        to_users = payload.get("to", [])
        if isinstance(to_users, str):
            to_users = [to_users]
        subject = payload.get("subject", "")
        body = payload.get("body", "")
        now = datetime.now(timezone.utc).isoformat()

        if draft_id:
            # 更新现有草稿
            existing = await self.db.fetchone(
                "SELECT * FROM emails WHERE email_id = ? AND from_user = ? AND status = 'DRAFT'",
                (draft_id, from_user)
            )
            if not existing:
                return build_response(request_id, StatusCode.NOT_FOUND, "草稿不存在")
            
            await self.db.execute(
                "UPDATE emails SET to_users = ?, subject = ?, body = ? WHERE email_id = ?",
                (json.dumps(to_users), subject, body, draft_id)
            )
            await self.db.commit()
            email_id = draft_id
        else:
            # 创建新草稿
            email_id = str(uuid.uuid4())
            await self.db.execute(
                """INSERT INTO emails (email_id, from_user, to_users, subject, body, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'DRAFT', ?)""",
                (email_id, from_user, json.dumps(to_users), subject, body, now)
            )
            await self.db.commit()

        return build_response(request_id, StatusCode.OK, "草稿已保存", {
            "draft_id": email_id
        })

    async def handle_list_drafts(self, msg: dict) -> dict:
        """处理草稿列表请求"""
        request_id = msg.get("request_id", "")
        token_payload = msg.get("_token_payload", {})

        username = token_payload.get("username", "")
        domain = token_payload.get("domain", self.domain)
        from_user = f"{username}@{domain}"

        rows = await self.db.fetchall(
            """SELECT email_id, to_users, subject, body, created_at
               FROM emails
               WHERE from_user = ? AND status = 'DRAFT'
               ORDER BY created_at DESC""",
            (from_user,)
        )

        drafts = []
        for row in (rows or []):
            d = dict(row)
            d["to"] = json.loads(d.pop("to_users"))
            drafts.append(d)

        return build_response(request_id, StatusCode.OK, "草稿箱", {
            "drafts": drafts
        })

    async def handle_recall_mail(self, msg: dict) -> dict:
        """处理邮件撤回请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        token_payload = msg.get("_token_payload", {})

        email_id = payload.get("email_id", "")
        signature = payload.get("signature", "")
        
        username = token_payload.get("username", "")
        domain = token_payload.get("domain", self.domain)
        from_user = f"{username}@{domain}"

        if not email_id:
            return build_response(request_id, StatusCode.BAD_REQUEST, "缺少 email_id")

        # 查找邮件
        email = await self.db.fetchone(
            "SELECT * FROM emails WHERE email_id = ?", (email_id,)
        )
        if not email:
            return build_response(request_id, StatusCode.NOT_FOUND, "邮件不存在")

        email_dict = dict(email)

        # 1. 身份校验：仅发送者可撤回
        if email_dict["from_user"] != from_user:
            return build_response(request_id, StatusCode.FORBIDDEN, "只有发件人可以撤回邮件")

        # 2. 幂等性：已撤回则直接返回成功
        if email_dict["status"] == "RECALLED":
            return build_response(request_id, StatusCode.OK, "邮件已撤回（重复操作）")

        # 3. 时间窗口校验（5分钟内）
        sent_at = datetime.fromisoformat(email_dict["sent_at"])
        recall_window = timedelta(minutes=self.config.security.recall_window_minutes)
        if datetime.now(timezone.utc) > sent_at + recall_window:
            return build_response(request_id, StatusCode.FORBIDDEN, "已超过撤回时间窗口（5分钟）")

        # 4. HMAC 签名验证
        expected_sig = compute_hmac(
            self.config.security.jwt_secret,
            f"RECALL:{email_id}:{from_user}"
        )
        if signature != expected_sig:
            return build_response(request_id, StatusCode.FORBIDDEN, "撤回签名验证失败")

        # 5. 执行撤回
        await self.db.execute(
            "UPDATE emails SET status = 'RECALLED' WHERE email_id = ?",
            (email_id,)
        )
        await self.db.execute(
            "UPDATE email_recipients SET is_recalled = 1 WHERE email_id = ?",
            (email_id,)
        )
        await self.db.commit()

        # 6. 检查是否已读
        read_row = await self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM email_recipients WHERE email_id = ? AND is_read = 1",
            (email_id,)
        )
        already_read = read_row["cnt"] > 0 if read_row else False

        msg_text = "邮件撤回成功"
        if already_read:
            msg_text += "（注意：部分收件人可能已阅读）"

        logger.info(f"邮件撤回: {email_id} by {from_user}")
        await self.audit.log_recall(from_user, email_id, success=True)
        return build_response(request_id, StatusCode.OK, msg_text, {
            "email_id": email_id,
            "already_read": already_read
        })

    async def handle_search_mail(self, msg: dict) -> dict:
        """处理邮件搜索请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        token_payload = msg.get("_token_payload", {})

        username = token_payload.get("username", "")
        domain = token_payload.get("domain", self.domain)
        user_email = f"{username}@{domain}"

        query = payload.get("query", "")
        limit = payload.get("limit", 20)

        if not query:
            return build_response(request_id, StatusCode.BAD_REQUEST, "搜索关键词不能为空")

        results = await self.search_engine.search(query, user_email, limit=limit)

        # 对搜索结果补充邮件摘要信息
        enriched = []
        for item in results:
            email = await self.db.fetchone(
                "SELECT email_id, from_user, subject, sent_at FROM emails WHERE email_id = ?",
                (item["email_id"],)
            )
            if email:
                enriched.append({
                    "email_id": item["email_id"],
                    "from": email["from_user"],
                    "subject": email["subject"],
                    "sent_at": email["sent_at"],
                    "score": item["score"],
                    "match_type": item["match_type"]
                })

        return build_response(request_id, StatusCode.OK, "搜索结果", {
            "query": query,
            "results": enriched,
            "total": len(enriched)
        })

    async def handle_quick_reply(self, msg: dict) -> dict:
        """处理快速回复建议请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        token_payload = msg.get("_token_payload", {})

        username = token_payload.get("username", "")
        domain = token_payload.get("domain", self.domain)
        user_email = f"{username}@{domain}"

        email_id = payload.get("email_id", "")
        if not email_id:
            return build_response(request_id, StatusCode.BAD_REQUEST, "缺少 email_id")

        # 查询邮件
        email = await self.db.fetchone(
            "SELECT e.email_id, e.from_user, e.subject, e.body, e.category "
            "FROM emails e "
            "JOIN email_recipients er ON e.email_id = er.email_id "
            "WHERE e.email_id = ? AND er.recipient = ?",
            (email_id, user_email)
        )
        if not email:
            return build_response(request_id, StatusCode.NOT_FOUND, "邮件不存在或无权访问")

        # 生成回复建议
        suggestions = self.quick_reply.generate_replies(
            email={"subject": email["subject"], "body": email["body"],
                   "from_user": email["from_user"]},
            category=email["category"]
        )

        return build_response(request_id, StatusCode.OK, "回复建议", {
            "email_id": email_id,
            "suggestions": suggestions
        })

    async def handle_exec_action(self, msg: dict) -> dict:
        """处理快捷操作执行请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        token_payload = msg.get("_token_payload", {})

        username = token_payload.get("username", "")
        domain = token_payload.get("domain", self.domain)
        user_email = f"{username}@{domain}"

        email_id = payload.get("email_id", "")
        action_index = payload.get("action_index")  # 操作索引
        confirm = payload.get("confirm", False)  # 二次确认标志

        if not email_id:
            return build_response(request_id, StatusCode.BAD_REQUEST, "缺少 email_id")
        if action_index is None:
            return build_response(request_id, StatusCode.BAD_REQUEST, "缺少 action_index")

        # 查询邮件及其 actions
        email = await self.db.fetchone(
            "SELECT e.email_id, e.actions "
            "FROM emails e "
            "JOIN email_recipients er ON e.email_id = er.email_id "
            "WHERE e.email_id = ? AND er.recipient = ?",
            (email_id, user_email)
        )
        if not email:
            return build_response(request_id, StatusCode.NOT_FOUND, "邮件不存在或无权访问")

        # 解析 actions
        actions_json = email["actions"]
        if not actions_json:
            return build_response(request_id, StatusCode.BAD_REQUEST, "该邮件没有可执行的快捷操作")

        try:
            actions_list = json.loads(actions_json)
        except (json.JSONDecodeError, TypeError):
            return build_response(request_id, StatusCode.BAD_REQUEST, "快捷操作数据格式错误")

        if not isinstance(action_index, int) or action_index < 0 or action_index >= len(actions_list):
            return build_response(request_id, StatusCode.BAD_REQUEST, f"无效的 action_index: {action_index}")

        action_def = actions_list[action_index]

        # 执行操作
        success, message, result = self.action_engine.execute_action(
            email_id, action_def, confirm=confirm
        )

        status = StatusCode.OK if success else StatusCode.BAD_REQUEST
        return build_response(request_id, status, message, result)
