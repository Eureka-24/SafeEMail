"""
消息路由与分发 - 根据 action 路由到对应处理函数
"""
import asyncio
import logging
from typing import Callable, Dict, Optional

from shared.protocol import Action, StatusCode, MessageType, build_response
from server.protocol.codec import MessageCodec
from server.protocol.actions import PUBLIC_ACTIONS

logger = logging.getLogger(__name__)


class MessageHandler:
    """消息路由分发器"""

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        # 注册内置处理器
        self._handlers[Action.PING] = self._handle_ping

    def register(self, action: str, handler: Callable):
        """注册 action 处理函数"""
        self._handlers[action] = handler

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理单个客户端连接"""
        peer = writer.get_extra_info("peername")
        logger.info(f"新连接: {peer}")
        
        codec = MessageCodec(reader, writer)
        
        try:
            while True:
                msg = await codec.read_message()
                if msg is None:
                    logger.info(f"连接关闭: {peer}")
                    break

                await self._dispatch(msg, codec, peer)
        except ValueError as e:
            logger.warning(f"协议错误 ({peer}): {e}")
        except Exception as e:
            logger.error(f"处理连接异常 ({peer}): {e}", exc_info=True)
        finally:
            codec.close()

    async def _dispatch(self, msg: dict, codec: MessageCodec, peer):
        """消息分发"""
        action = msg.get("action")
        request_id = msg.get("request_id", "")
        msg_type = msg.get("type")

        # 验证消息格式
        if msg_type not in (MessageType.REQUEST, MessageType.S2S_REQUEST):
            response = build_response(request_id, StatusCode.BAD_REQUEST, "无效的消息类型")
            await codec.write_message(response)
            return

        # 查找处理器
        handler = self._handlers.get(action)
        if handler is None:
            response = build_response(request_id, StatusCode.BAD_REQUEST, f"未知的 action: {action}")
            await codec.write_message(response)
            return

        # 调用处理器
        try:
            response = await handler(msg)
            if response:
                await codec.write_message(response)
        except Exception as e:
            logger.error(f"处理 {action} 异常: {e}", exc_info=True)
            response = build_response(request_id, StatusCode.INTERNAL_ERROR, "服务器内部错误")
            await codec.write_message(response)

    async def _handle_ping(self, msg: dict) -> dict:
        """处理 PING 请求，返回 PONG"""
        return build_response(
            msg.get("request_id", ""),
            StatusCode.OK,
            "PONG",
            {"action": Action.PONG}
        )
