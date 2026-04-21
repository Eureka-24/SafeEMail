"""
JWT 签发与验证工具
"""
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional


class JWTUtil:
    """JWT 工具类"""

    def __init__(self, secret: str, access_expire_minutes: int = 30, refresh_expire_days: int = 7):
        self.secret = secret
        self.access_expire_minutes = access_expire_minutes
        self.refresh_expire_days = refresh_expire_days
        self.algorithm = "HS256"

    def create_access_token(self, user_id: str, username: str, domain: str) -> tuple[str, str]:
        """
        创建 Access Token
        
        Returns:
            (token_string, jti)
        """
        jti = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "username": username,
            "domain": domain,
            "jti": jti,
            "iat": now,
            "exp": now + timedelta(minutes=self.access_expire_minutes),
            "type": "access"
        }
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        return token, jti

    def create_refresh_token(self, user_id: str) -> tuple[str, str]:
        """
        创建 Refresh Token
        
        Returns:
            (token_string, jti)
        """
        jti = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "jti": jti,
            "iat": now,
            "exp": now + timedelta(days=self.refresh_expire_days),
            "type": "refresh"
        }
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        return token, jti

    def verify_token(self, token: str) -> Optional[dict]:
        """
        验证并解码 Token
        
        Returns:
            解码后的 payload，无效时返回 None
        """
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    def get_token_expiry(self, token: str) -> Optional[str]:
        """获取 token 的过期时间（ISO 格式）"""
        payload = self.verify_token(token)
        if payload and "exp" in payload:
            return datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat()
        return None
