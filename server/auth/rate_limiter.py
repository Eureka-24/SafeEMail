"""
暴力破解防护 / 速率限制
"""
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from server.storage.models import UserModel, RateLimitModel


class RateLimiter:
    """登录速率限制器"""

    def __init__(self, user_model: UserModel, rate_model: RateLimitModel, config):
        self.user_model = user_model
        self.rate_model = rate_model
        self.max_ip_attempts = config.max_login_attempts_ip  # 5
        self.ip_lockout_minutes = config.ip_lockout_minutes  # 15
        self.max_account_attempts = config.max_login_attempts_account  # 10
        self.account_lockout_minutes = config.account_lockout_minutes  # 30
        self.captcha_threshold = 3  # 3次失败后触发验证码

    async def check_ip_rate(self, ip_address: str) -> Tuple[bool, str]:
        """
        检查 IP 级别速率限制
        
        Returns:
            (是否允许, 错误消息)
        """
        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        count = await self.rate_model.get_attempt_count(ip_address, "LOGIN", since)
        
        if count >= self.max_ip_attempts:
            return False, f"IP 已被锁定，请 {self.ip_lockout_minutes} 分钟后重试"
        
        return True, ""

    async def check_account_rate(self, username: str) -> Tuple[bool, str]:
        """
        检查账号级别速率限制
        
        Returns:
            (是否允许, 错误消息)
        """
        user = await self.user_model.get_user_by_username(username)
        if not user:
            return True, ""
        
        # 检查是否被锁定
        if user["status"] == "LOCKED" and user["locked_until"]:
            locked_until = datetime.fromisoformat(user["locked_until"])
            if datetime.now(timezone.utc) < locked_until:
                return False, f"账号已锁定至 {user['locked_until']}"
            else:
                # 锁定时间已过，解锁
                await self.user_model.unlock_user(username)
        
        return True, ""

    async def record_failed_attempt(self, ip_address: str, username: str):
        """记录一次失败的登录尝试"""
        # 记录 IP 级别
        await self.rate_model.record_attempt(ip_address, "LOGIN")
        
        # 更新账号级别
        user = await self.user_model.get_user_by_username(username)
        if user:
            new_count = user["failed_attempts"] + 1
            if new_count >= self.max_account_attempts:
                locked_until = (datetime.now(timezone.utc) + timedelta(minutes=self.account_lockout_minutes)).isoformat()
                await self.user_model.update_failed_attempts(username, new_count, locked_until)
            else:
                await self.user_model.update_failed_attempts(username, new_count)

    async def needs_captcha(self, ip_address: str) -> bool:
        """检查是否需要验证码"""
        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        count = await self.rate_model.get_attempt_count(ip_address, "LOGIN", since)
        return count >= self.captcha_threshold

    def generate_captcha(self) -> Tuple[str, int]:
        """
        生成简单数学验证码
        
        Returns:
            (题目, 正确答案)
        """
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        op = random.choice(["+", "-", "*"])
        
        if op == "+":
            answer = a + b
        elif op == "-":
            answer = a - b
        else:
            answer = a * b
        
        question = f"{a} {op} {b} = ?"
        return question, answer

    async def record_success(self, username: str):
        """记录登录成功，重置失败计数"""
        await self.user_model.reset_failed_attempts(username)
