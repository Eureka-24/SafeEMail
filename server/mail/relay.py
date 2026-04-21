"""
S2S 跨域中继 - 服务器间 TLS 连接、邮件投递与撤回
"""
import asyncio
import json
import logging
import ssl
from typing import Optional

from shared.protocol import (
    PROTOCOL_VERSION, MessageType, Action, StatusCode,
    MESSAGE_DELIMITER, build_response
)
from shared.crypto import compute_hmac
from server.storage.database import Database
from server.config import ServerConfig
from server.security.tls import create_client_ssl_context

logger = logging.getLogger(__name__)


class RelayClient:
    """S2S 中继客户端 - 向对端服务器发送请求"""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.shared_secret = config.s2s.shared_secret
        self.server_id = config.domain
        self._ssl_ctx = self._create_ssl_context()

    def _create_ssl_context(self) -> ssl.SSLContext:
        """创建 TLS 上下文（用于 S2S 连接）"""
        tls = self.config.tls
        if tls.ca_file:
            # 生产环境：使用 CA 证书验证
            return create_client_ssl_context(tls.ca_file)
        else:
            # 开发环境：不验证证书
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx

    async def deliver_mail(self, target_domain: str, email_data: dict) -> bool:
        """
        向目标域投递邮件
        
        Args:
            target_domain: 目标域名
            email_data: 完整邮件数据
            
        Returns:
            是否投递成功
        """
        peer = self._find_peer(target_domain)
        if not peer:
            logger.error(f"未找到对端配置: {target_domain}")
            return False

        # 构造 S2S 请求
        payload_str = json.dumps(email_data, ensure_ascii=False)
        signature = compute_hmac(self.shared_secret, f"S2S_DELIVER:{self.server_id}:{payload_str}")

        request = {
            "version": PROTOCOL_VERSION,
            "type": MessageType.S2S_REQUEST,
            "action": Action.S2S_DELIVER,
            "server_id": self.server_id,
            "signature": signature,
            "payload": {"email": email_data}
        }

        return await self._send_to_peer(peer, request)

    async def recall_mail(self, target_domain: str, email_id: str, from_user: str) -> bool:
        """
        向目标域发送撤回请求
        
        Args:
            target_domain: 目标域名
            email_id: 邮件ID
            from_user: 发件人地址
            
        Returns:
            是否撤回成功
        """
        peer = self._find_peer(target_domain)
        if not peer:
            logger.error(f"未找到对端配置: {target_domain}")
            return False

        payload_data = {"email_id": email_id, "from_user": from_user}
        payload_str = json.dumps(payload_data, ensure_ascii=False)
        signature = compute_hmac(self.shared_secret, f"S2S_RECALL:{self.server_id}:{payload_str}")

        request = {
            "version": PROTOCOL_VERSION,
            "type": MessageType.S2S_REQUEST,
            "action": Action.S2S_RECALL,
            "server_id": self.server_id,
            "signature": signature,
            "payload": payload_data
        }

        return await self._send_to_peer(peer, request)

    async def _send_to_peer(self, peer, request: dict) -> bool:
        """向对端发送请求并等待响应"""
        try:
            # 建立 TLS 连接
            reader, writer = await asyncio.open_connection(
                peer.host, peer.port,
                ssl=self._ssl_ctx
            )

            # 发送请求
            data = json.dumps(request, ensure_ascii=False).encode("utf-8") + MESSAGE_DELIMITER
            writer.write(data)
            await writer.drain()

            # 读取响应
            response_data = await asyncio.wait_for(reader.readuntil(MESSAGE_DELIMITER), timeout=10.0)
            response = json.loads(response_data.decode("utf-8").strip())

            writer.close()
            await writer.wait_closed()

            if response.get("status") == StatusCode.OK:
                logger.info(f"S2S 请求成功: {request['action']} -> {peer.domain}")
                return True
            else:
                logger.warning(f"S2S 请求失败: {response.get('message', 'unknown')}")
                return False

        except asyncio.TimeoutError:
            logger.error(f"S2S 连接超时: {peer.domain}:{peer.port}")
            return False
        except (ConnectionRefusedError, OSError) as e:
            logger.error(f"S2S 连接失败: {peer.domain}:{peer.port} - {e}")
            return False
        except Exception as e:
            logger.error(f"S2S 请求异常: {e}", exc_info=True)
            return False

    def _find_peer(self, domain: str):
        """查找对端配置"""
        for peer in self.config.s2s.peers:
            if peer.domain == domain:
                return peer
        return None


class RelayHandler:
    """S2S 中继处理器 - 处理来自对端服务器的请求"""

    def __init__(self, db: Database, config: ServerConfig):
        self.db = db
        self.config = config
        self.shared_secret = config.s2s.shared_secret
        self.domain = config.domain

    async def handle_s2s_deliver(self, msg: dict) -> dict:
        """处理 S2S 邮件投递请求"""
        request_id = msg.get("request_id", "")
        server_id = msg.get("server_id", "")
        signature = msg.get("signature", "")
        payload = msg.get("payload", {})

        # 验证 HMAC 签名
        email_data = payload.get("email", {})
        payload_str = json.dumps(email_data, ensure_ascii=False)
        expected_sig = compute_hmac(self.shared_secret, f"S2S_DELIVER:{server_id}:{payload_str}")

        if signature != expected_sig:
            logger.warning(f"S2S 签名验证失败: {server_id}")
            return build_response(request_id, StatusCode.FORBIDDEN, "签名验证失败")

        # 写入本地数据库
        email_id = email_data.get("email_id", "")
        from_user = email_data.get("from_user", "")
        to_users = email_data.get("to_users", [])
        subject = email_data.get("subject", "")
        body = email_data.get("body", "")
        sent_at = email_data.get("sent_at", "")
        created_at = email_data.get("created_at", sent_at)

        # 插入邮件
        await self.db.execute(
            """INSERT OR IGNORE INTO emails (email_id, from_user, to_users, subject, body, status, created_at, sent_at)
               VALUES (?, ?, ?, ?, ?, 'SENT', ?, ?)""",
            (email_id, from_user, json.dumps(to_users), subject, body, created_at, sent_at)
        )

        # 插入本域收件人记录
        for recipient in to_users:
            if "@" in recipient:
                _, domain = recipient.split("@", 1)
                if domain == self.domain:
                    await self.db.execute(
                        "INSERT OR IGNORE INTO email_recipients (email_id, recipient, is_read, is_recalled) VALUES (?, ?, 0, 0)",
                        (email_id, recipient)
                    )

        await self.db.commit()
        logger.info(f"S2S 邮件投递成功: {email_id} from {server_id}")
        return build_response(request_id, StatusCode.OK, "投递成功")

    async def handle_s2s_recall(self, msg: dict) -> dict:
        """处理 S2S 撤回请求"""
        request_id = msg.get("request_id", "")
        server_id = msg.get("server_id", "")
        signature = msg.get("signature", "")
        payload = msg.get("payload", {})

        # 验证签名
        payload_str = json.dumps(payload, ensure_ascii=False)
        expected_sig = compute_hmac(self.shared_secret, f"S2S_RECALL:{server_id}:{payload_str}")

        if signature != expected_sig:
            logger.warning(f"S2S 撤回签名验证失败: {server_id}")
            return build_response(request_id, StatusCode.FORBIDDEN, "签名验证失败")

        email_id = payload.get("email_id", "")
        from_user = payload.get("from_user", "")

        # 验证邮件存在且发件人匹配
        email = await self.db.fetchone(
            "SELECT from_user FROM emails WHERE email_id = ?", (email_id,)
        )
        if not email:
            return build_response(request_id, StatusCode.NOT_FOUND, "邮件不存在")

        if dict(email)["from_user"] != from_user:
            return build_response(request_id, StatusCode.FORBIDDEN, "发件人不匹配")

        # 执行撤回
        await self.db.execute(
            "UPDATE emails SET status = 'RECALLED' WHERE email_id = ?", (email_id,)
        )
        await self.db.execute(
            "UPDATE email_recipients SET is_recalled = 1 WHERE email_id = ?", (email_id,)
        )
        await self.db.commit()

        logger.info(f"S2S 撤回成功: {email_id} from {server_id}")
        return build_response(request_id, StatusCode.OK, "撤回成功")
