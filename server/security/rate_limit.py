"""
发送频率限制 - 滑动窗口算法
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple

from server.storage.database import Database

logger = logging.getLogger(__name__)


class SendRateLimiter:
    """邮件发送频率限制器（滑动窗口）"""

    def __init__(self, db: Database, config):
        self.db = db
        self.max_per_minute = config.max_send_per_minute   # 10
        self.max_per_hour = config.max_send_per_hour       # 60

    async def check_send_rate(self, username: str) -> Tuple[bool, str]:
        """
        检查用户发送频率是否超限
        
        Args:
            username: 发件人用户名（含域名，如 alice@alpha.local）
            
        Returns:
            (是否允许, 错误消息)
        """
        now = datetime.now(timezone.utc)

        # 检查每分钟限制
        since_1min = (now - timedelta(minutes=1)).isoformat()
        count_1min = await self._get_send_count(username, since_1min)
        if count_1min >= self.max_per_minute:
            logger.warning(f"发送频率超限(分钟): {username}, count={count_1min}")
            return False, f"发送过于频繁，每分钟最多 {self.max_per_minute} 封"

        # 检查每小时限制
        since_1hour = (now - timedelta(hours=1)).isoformat()
        count_1hour = await self._get_send_count(username, since_1hour)
        if count_1hour >= self.max_per_hour:
            logger.warning(f"发送频率超限(小时): {username}, count={count_1hour}")
            return False, f"发送过于频繁，每小时最多 {self.max_per_hour} 封"

        return True, ""

    async def record_send(self, username: str):
        """记录一次发送"""
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "INSERT INTO send_rate_limits (username, send_time) VALUES (?, ?)",
            (username, now)
        )
        await self.db.commit()

    async def _get_send_count(self, username: str, since: str) -> int:
        """获取指定时间段内的发送次数"""
        row = await self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM send_rate_limits WHERE username = ? AND send_time > ?",
            (username, since)
        )
        return row["cnt"] if row else 0

    async def cleanup_old_records(self):
        """清理超过 2 小时的旧记录"""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        await self.db.execute(
            "DELETE FROM send_rate_limits WHERE send_time < ?", (cutoff,)
        )
        await self.db.commit()
