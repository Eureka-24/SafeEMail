"""
审计日志记录 - 所有关键操作的审计追踪

记录到 audit_logs 表，格式：
{log_id, timestamp, user_id, action, ip_address, detail(JSON), level}
"""
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from server.storage.database import Database

logger = logging.getLogger(__name__)


class AuditLogger:
    """审计日志记录器"""

    def __init__(self, db: Database):
        self.db = db

    async def log(self, action: str, user_id: str = None,
                  ip_address: str = None, detail: dict = None,
                  level: str = "INFO"):
        """
        记录审计日志

        Args:
            action: 操作类型（LOGIN/REGISTER/SEND_MAIL/RECALL/RATE_LIMIT 等）
            user_id: 操作用户（可选）
            ip_address: 客户端 IP（可选）
            detail: 详细信息（JSON 序列化）
            level: 日志级别 INFO/WARN/ERROR
        """
        log_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        detail_json = json.dumps(detail, ensure_ascii=False) if detail else None

        try:
            await self.db.execute(
                """INSERT INTO audit_logs (log_id, timestamp, user_id, action, ip_address, detail, level)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (log_id, timestamp, user_id, action, ip_address, detail_json, level)
            )
            await self.db.commit()
        except Exception as e:
            # 审计日志写入失败不应阻塞业务流程
            logger.error(f"审计日志写入失败: {e}")

    async def log_login(self, username: str, success: bool, ip_address: str = None,
                        reason: str = None):
        """记录登录事件"""
        await self.log(
            action="LOGIN",
            user_id=username,
            ip_address=ip_address,
            detail={"success": success, "reason": reason},
            level="INFO" if success else "WARN"
        )

    async def log_register(self, username: str, success: bool, reason: str = None):
        """记录注册事件"""
        await self.log(
            action="REGISTER",
            user_id=username,
            detail={"success": success, "reason": reason},
            level="INFO" if success else "WARN"
        )

    async def log_send_mail(self, from_user: str, to_users: list, email_id: str,
                            is_spam: bool = False):
        """记录邮件发送事件"""
        await self.log(
            action="SEND_MAIL",
            user_id=from_user,
            detail={
                "email_id": email_id,
                "to_users": to_users,
                "is_spam": is_spam
            }
        )

    async def log_recall(self, from_user: str, email_id: str, success: bool,
                         reason: str = None):
        """记录邮件撤回事件"""
        await self.log(
            action="RECALL_MAIL",
            user_id=from_user,
            detail={"email_id": email_id, "success": success, "reason": reason},
            level="INFO" if success else "WARN"
        )

    async def log_rate_limit(self, user_id: str, action_type: str,
                             ip_address: str = None):
        """记录限流触发事件"""
        await self.log(
            action="RATE_LIMIT",
            user_id=user_id,
            ip_address=ip_address,
            detail={"triggered_by": action_type},
            level="WARN"
        )

    async def log_error(self, action: str, error: str, user_id: str = None):
        """记录系统错误"""
        await self.log(
            action=action,
            user_id=user_id,
            detail={"error": error},
            level="ERROR"
        )

    async def query_logs(self, action: str = None, user_id: str = None,
                         level: str = None, limit: int = 50) -> list:
        """查询审计日志"""
        sql = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if action:
            sql += " AND action = ?"
            params.append(action)
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        if level:
            sql += " AND level = ?"
            params.append(level)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = await self.db.fetchall(sql, tuple(params))
        return [dict(row) for row in rows] if rows else []
