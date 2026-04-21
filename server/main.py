"""
服务器启动入口 - 根据配置启动服务器实例
"""
import asyncio
import logging
import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from server.config import load_config, ServerConfig
from server.protocol.handler import MessageHandler
from server.storage.database import Database
from server.storage.migrations import run_migrations
from server.auth.service import AuthService
from server.mail.service import MailService
from server.mail.group import GroupService
from server.mail.relay import RelayClient, RelayHandler
from server.storage.attachment import AttachmentService
from shared.protocol import Action, StatusCode, build_response

logger = logging.getLogger(__name__)


class EmailServer:
    """邮件服务器"""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.handler = MessageHandler()
        self.db = Database(config.data_dir)
        self.auth_service = None
        self._server = None

    async def _init_services(self):
        """初始化数据库和服务"""
        await self.db.connect()
        await run_migrations(self.db)
        
        # 初始化认证服务
        self.auth_service = AuthService(self.db, self.config)
        
        # 初始化邮件服务
        self.mail_service = MailService(self.db, self.config)
        self.group_service = GroupService(self.db, self.config)
        self.relay_client = RelayClient(self.config)
        self.relay_handler = RelayHandler(self.db, self.config)
        self.mail_service.relay_client = self.relay_client
        self.attachment_service = AttachmentService(self.db, self.config)
        
        # 注册认证处理器
        self.handler.register(Action.REGISTER, self.auth_service.handle_register)
        self.handler.register(Action.LOGIN, self._handle_login)
        self.handler.register(Action.LOGOUT, self.auth_service.handle_logout)
        self.handler.register(Action.REFRESH, self.auth_service.handle_refresh)
        
        # 注册邮件处理器（需要认证）
        self.handler.register(Action.SEND_MAIL, self._auth_wrap(self.mail_service.handle_send_mail))
        self.handler.register(Action.LIST_INBOX, self._auth_wrap(self.mail_service.handle_list_inbox))
        self.handler.register(Action.READ_MAIL, self._auth_wrap(self.mail_service.handle_read_mail))
        self.handler.register(Action.LIST_SENT, self._auth_wrap(self.mail_service.handle_list_sent))
        self.handler.register(Action.SAVE_DRAFT, self._auth_wrap(self.mail_service.handle_save_draft))
        self.handler.register(Action.LIST_DRAFTS, self._auth_wrap(self.mail_service.handle_list_drafts))
        self.handler.register(Action.RECALL_MAIL, self._auth_wrap(self.mail_service.handle_recall_mail))
        self.handler.register(Action.SEARCH_MAIL, self._auth_wrap(self.mail_service.handle_search_mail))
        
        # 注册群组处理器
        self.handler.register(Action.CREATE_GROUP, self._auth_wrap(self.group_service.handle_create_group))
        self.handler.register(Action.LIST_GROUPS, self._auth_wrap(self.group_service.handle_list_groups))
        
        # 注册 S2S 处理器
        self.handler.register(Action.S2S_DELIVER, self.relay_handler.handle_s2s_deliver)
        self.handler.register(Action.S2S_RECALL, self.relay_handler.handle_s2s_recall)
        
        # 注册附件处理器
        self.handler.register(Action.UPLOAD_ATTACH, self._auth_wrap(self._handle_upload_attach))
        self.handler.register(Action.DOWNLOAD_ATTACH, self._auth_wrap(self._handle_download_attach))

        # 注册快捷操作处理器
        self.handler.register(Action.QUICK_REPLY, self._auth_wrap(self.mail_service.handle_quick_reply))
        self.handler.register(Action.EXEC_ACTION, self._auth_wrap(self.mail_service.handle_exec_action))

    def _auth_wrap(self, handler):
        """认证中间件包装器"""
        async def wrapped(msg: dict) -> dict:
            token = msg.get("token", "")
            valid, payload, err = await self.auth_service.verify_request_token(token)
            if not valid:
                return build_response(msg.get("request_id", ""), StatusCode.UNAUTHORIZED, err)
            msg["_token_payload"] = payload
            return await handler(msg)
        return wrapped

    async def _handle_login(self, msg: dict) -> dict:
        """登录处理（提取 IP 地址）"""
        # TODO: 从连接上下文获取真实 IP
        return await self.auth_service.handle_login(msg, ip_address="127.0.0.1")

    async def _handle_upload_attach(self, msg: dict) -> dict:
        """处理附件上传"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        email_id = payload.get("email_id", "")
        filename = payload.get("filename", "")
        content_type = payload.get("content_type", "application/octet-stream")
        data = payload.get("data", "")

        if not email_id or not filename or not data:
            return build_response(request_id, StatusCode.BAD_REQUEST, "缺少必要参数")

        success, msg_text, info = await self.attachment_service.upload(
            email_id, filename, content_type, data
        )
        if success:
            return build_response(request_id, StatusCode.CREATED, "上传成功", info)
        else:
            return build_response(request_id, StatusCode.BAD_REQUEST, msg_text)

    async def _handle_download_attach(self, msg: dict) -> dict:
        """处理附件下载"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        attachment_id = payload.get("attachment_id", "")

        if not attachment_id:
            return build_response(request_id, StatusCode.BAD_REQUEST, "缺少 attachment_id")

        success, msg_text, info = await self.attachment_service.download(attachment_id)
        if success:
            return build_response(request_id, StatusCode.OK, msg_text, info)
        else:
            return build_response(request_id, StatusCode.NOT_FOUND, msg_text)

    async def start(self):
        """启动服务器"""
        # 确保数据目录存在
        os.makedirs(self.config.data_dir, exist_ok=True)
        
        # 初始化服务
        await self._init_services()

        self._server = await asyncio.start_server(
            self.handler.handle_connection,
            self.config.host,
            self.config.port
        )

        addr = self._server.sockets[0].getsockname()
        logger.info(f"服务器 [{self.config.domain}] 启动于 {addr[0]}:{addr[1]}")

        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        """停止服务器"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info(f"服务器 [{self.config.domain}] 已停止")


def setup_logging(domain: str):
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{domain}] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python -m server.main <config_path>")
        print("示例: python -m server.main config/alpha.yaml")
        sys.exit(1)

    config_path = sys.argv[1]

    # 根据配置文件路径加载对应的 .env 文件
    # 例如 config/alpha.yaml -> config/alpha.env
    env_path = os.path.splitext(config_path)[0] + ".env"
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
        print(f"已加载环境变量: {env_path}")

    config = load_config(config_path)

    setup_logging(config.domain)
    logger.info(f"加载配置: {config_path}")
    logger.info(f"域名: {config.domain}, 端口: {config.port}")

    server = EmailServer(config)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")


if __name__ == "__main__":
    main()
