"""
数据模型 - 数据访问层 CRUD 方法
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, List

from server.storage.database import Database


class UserModel:
    """用户数据访问"""

    def __init__(self, db: Database):
        self.db = db

    async def create_user(self, username: str, password_hash: str, domain: str) -> str:
        """创建用户，返回 user_id"""
        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        await self.db.execute(
            "INSERT INTO users (user_id, username, password_hash, domain, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, password_hash, domain, created_at)
        )
        await self.db.commit()
        return user_id

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """根据用户名查询用户"""
        row = await self.db.fetchone(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        return dict(row) if row else None

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """根据 ID 查询用户"""
        row = await self.db.fetchone(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        return dict(row) if row else None

    async def update_failed_attempts(self, username: str, count: int, locked_until: str = None):
        """更新失败尝试次数"""
        if locked_until:
            await self.db.execute(
                "UPDATE users SET failed_attempts = ?, locked_until = ?, status = 'LOCKED' WHERE username = ?",
                (count, locked_until, username)
            )
        else:
            await self.db.execute(
                "UPDATE users SET failed_attempts = ? WHERE username = ?",
                (count, username)
            )
        await self.db.commit()

    async def reset_failed_attempts(self, username: str):
        """重置失败次数"""
        await self.db.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL, status = 'ACTIVE' WHERE username = ?",
            (username,)
        )
        await self.db.commit()

    async def unlock_user(self, username: str):
        """解锁用户"""
        await self.reset_failed_attempts(username)


class TokenBlacklistModel:
    """Token 黑名单数据访问"""

    def __init__(self, db: Database):
        self.db = db

    async def add_to_blacklist(self, jti: str, expired_at: str):
        """将 Token 加入黑名单"""
        await self.db.execute(
            "INSERT OR IGNORE INTO token_blacklist (jti, expired_at) VALUES (?, ?)",
            (jti, expired_at)
        )
        await self.db.commit()

    async def is_blacklisted(self, jti: str) -> bool:
        """检查 Token 是否在黑名单中"""
        row = await self.db.fetchone(
            "SELECT jti FROM token_blacklist WHERE jti = ?", (jti,)
        )
        return row is not None

    async def cleanup_expired(self):
        """清理过期的黑名单记录"""
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "DELETE FROM token_blacklist WHERE expired_at < ?", (now,)
        )
        await self.db.commit()


class RateLimitModel:
    """IP 限流记录数据访问"""

    def __init__(self, db: Database):
        self.db = db

    async def record_attempt(self, ip_address: str, action_type: str):
        """记录一次尝试"""
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "INSERT INTO ip_rate_limits (ip_address, attempt_time, action_type) VALUES (?, ?, ?)",
            (ip_address, now, action_type)
        )
        await self.db.commit()

    async def get_attempt_count(self, ip_address: str, action_type: str, since: str) -> int:
        """获取指定时间段内的尝试次数"""
        row = await self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM ip_rate_limits WHERE ip_address = ? AND action_type = ? AND attempt_time > ?",
            (ip_address, action_type, since)
        )
        return row["cnt"] if row else 0

    async def cleanup_old_records(self, before: str):
        """清理旧记录"""
        await self.db.execute(
            "DELETE FROM ip_rate_limits WHERE attempt_time < ?", (before,)
        )
        await self.db.commit()
