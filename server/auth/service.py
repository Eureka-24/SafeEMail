"""
认证服务 - 注册/登录/登出/Token 管理
"""
import logging
from datetime import datetime, timezone

from shared.protocol import Action, StatusCode, build_response
from server.auth.password import validate_password, hash_password, verify_password
from server.auth.jwt_util import JWTUtil
from server.auth.rate_limiter import RateLimiter
from server.storage.models import UserModel, TokenBlacklistModel, RateLimitModel
from server.storage.database import Database
from server.config import ServerConfig
from server.audit.logger import AuditLogger

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务"""

    def __init__(self, db: Database, config: ServerConfig):
        self.db = db
        self.config = config
        self.audit = AuditLogger(db)
        self.user_model = UserModel(db)
        self.blacklist_model = TokenBlacklistModel(db)
        self.rate_model = RateLimitModel(db)
        self.jwt_util = JWTUtil(
            secret=config.security.jwt_secret,
            access_expire_minutes=config.security.jwt_access_expire_minutes,
            refresh_expire_days=config.security.jwt_refresh_expire_days
        )
        self.rate_limiter = RateLimiter(self.user_model, self.rate_model, config.security)

    async def handle_register(self, msg: dict) -> dict:
        """处理注册请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        username = payload.get("username", "").strip()
        password = payload.get("password", "")

        # 验证用户名
        if not username or len(username) < 3:
            return build_response(request_id, StatusCode.BAD_REQUEST, "用户名长度不能少于3位")

        # 验证密码强度
        valid, err_msg = validate_password(password)
        if not valid:
            return build_response(request_id, StatusCode.BAD_REQUEST, err_msg)

        # 检查用户名唯一性
        existing = await self.user_model.get_user_by_username(username)
        if existing:
            return build_response(request_id, StatusCode.CONFLICT, "用户名已存在")

        # 创建用户
        password_hash = hash_password(password, self.config.security.bcrypt_cost)
        user_id = await self.user_model.create_user(username, password_hash, self.config.domain)

        logger.info(f"用户注册成功: {username} ({user_id})")
        await self.audit.log_register(username, success=True)
        return build_response(request_id, StatusCode.CREATED, "注册成功", {
            "user_id": user_id,
            "username": username,
            "domain": self.config.domain
        })

    async def handle_login(self, msg: dict, ip_address: str = "127.0.0.1") -> dict:
        """处理登录请求"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        username = payload.get("username", "").strip()
        password = payload.get("password", "")

        # 检查 IP 速率限制
        allowed, err_msg = await self.rate_limiter.check_ip_rate(ip_address)
        if not allowed:
            await self.audit.log_rate_limit(username, "LOGIN_IP", ip_address=ip_address)
            return build_response(request_id, StatusCode.TOO_MANY_REQUESTS, err_msg)

        # 检查账号速率限制
        allowed, err_msg = await self.rate_limiter.check_account_rate(username)
        if not allowed:
            await self.audit.log_rate_limit(username, "LOGIN_ACCOUNT", ip_address=ip_address)
            return build_response(request_id, StatusCode.TOO_MANY_REQUESTS, err_msg)

        # 查找用户
        user = await self.user_model.get_user_by_username(username)
        if not user:
            await self.rate_limiter.record_failed_attempt(ip_address, username)
            await self.audit.log_login(username, success=False, ip_address=ip_address, reason="用户不存在")
            return build_response(request_id, StatusCode.UNAUTHORIZED, "用户名或密码错误")

        # 验证密码
        if not verify_password(password, user["password_hash"]):
            await self.rate_limiter.record_failed_attempt(ip_address, username)
            
            # 检查是否需要验证码
            needs_captcha = await self.rate_limiter.needs_captcha(ip_address)
            resp_payload = {}
            if needs_captcha:
                question, answer = self.rate_limiter.generate_captcha()
                resp_payload["captcha_required"] = True
                resp_payload["captcha_question"] = question
                # 注意：实际中应将答案存储在服务端会话中
            
            await self.audit.log_login(username, success=False, ip_address=ip_address, reason="密码错误")
            return build_response(request_id, StatusCode.UNAUTHORIZED, "用户名或密码错误", resp_payload)

        # 登录成功，签发 Token
        await self.rate_limiter.record_success(username)
        
        access_token, access_jti = self.jwt_util.create_access_token(
            user["user_id"], username, self.config.domain
        )
        refresh_token, refresh_jti = self.jwt_util.create_refresh_token(user["user_id"])

        logger.info(f"用户登录成功: {username}")
        await self.audit.log_login(username, success=True, ip_address=ip_address)
        return build_response(request_id, StatusCode.OK, "登录成功", {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user["user_id"],
            "username": username,
            "domain": self.config.domain
        })

    async def handle_logout(self, msg: dict) -> dict:
        """处理登出请求"""
        request_id = msg.get("request_id", "")
        token = msg.get("token", "")

        if not token:
            return build_response(request_id, StatusCode.UNAUTHORIZED, "未提供 Token")

        payload = self.jwt_util.verify_token(token)
        if not payload:
            return build_response(request_id, StatusCode.UNAUTHORIZED, "无效的 Token")

        # 检查是否已在黑名单
        jti = payload.get("jti", "")
        if await self.blacklist_model.is_blacklisted(jti):
            return build_response(request_id, StatusCode.UNAUTHORIZED, "Token 已被撤销")

        # 将 Token 加入黑名单
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat()
        await self.blacklist_model.add_to_blacklist(jti, exp)

        logger.info(f"用户登出: {payload.get('username', 'unknown')}")
        return build_response(request_id, StatusCode.OK, "登出成功")

    async def handle_refresh(self, msg: dict) -> dict:
        """处理 Token 续期请求"""
        request_id = msg.get("request_id", "")
        payload_data = msg.get("payload", {})
        refresh_token = payload_data.get("refresh_token", "")

        if not refresh_token:
            return build_response(request_id, StatusCode.BAD_REQUEST, "未提供 Refresh Token")

        # 验证 Refresh Token
        token_payload = self.jwt_util.verify_token(refresh_token)
        if not token_payload:
            return build_response(request_id, StatusCode.UNAUTHORIZED, "Refresh Token 无效或已过期")

        if token_payload.get("type") != "refresh":
            return build_response(request_id, StatusCode.BAD_REQUEST, "非 Refresh Token")

        # 检查是否在黑名单
        jti = token_payload.get("jti", "")
        if await self.blacklist_model.is_blacklisted(jti):
            return build_response(request_id, StatusCode.UNAUTHORIZED, "Token 已被撤销")

        # 查询用户信息
        user_id = token_payload.get("sub", "")
        user = await self.user_model.get_user_by_id(user_id)
        if not user:
            return build_response(request_id, StatusCode.UNAUTHORIZED, "用户不存在")

        # 签发新的 Access Token
        access_token, _ = self.jwt_util.create_access_token(
            user["user_id"], user["username"], user["domain"]
        )

        return build_response(request_id, StatusCode.OK, "Token 续期成功", {
            "access_token": access_token
        })

    async def verify_request_token(self, token: str) -> tuple[bool, dict, str]:
        """
        验证请求中的 Token（中间件使用）
        
        Returns:
            (是否有效, payload, 错误消息)
        """
        if not token:
            return False, {}, "未提供认证 Token"

        payload = self.jwt_util.verify_token(token)
        if not payload:
            return False, {}, "Token 无效或已过期"

        if payload.get("type") != "access":
            return False, {}, "非 Access Token"

        # 检查黑名单
        jti = payload.get("jti", "")
        if await self.blacklist_model.is_blacklisted(jti):
            return False, {}, "Token 已被撤销"

        return True, payload, ""
