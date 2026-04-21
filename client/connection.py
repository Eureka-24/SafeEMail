"""
客户端 TCP 连接管理 - 异步收发消息
"""
import asyncio
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.protocol import MESSAGE_DELIMITER, MAX_MESSAGE_SIZE, build_request

logger = logging.getLogger(__name__)


class Connection:
    """客户端 TCP 连接管理"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8001):
        self.host = host
        self.port = port
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self._buffer = b""

    async def connect(self, use_tls: bool = False, ssl_context=None):
        """建立 TCP 连接"""
        self.reader, self.writer = await asyncio.open_connection(
            self.host, self.port, ssl=ssl_context if use_tls else None
        )
        logger.info(f"已连接到 {self.host}:{self.port}")

    async def send(self, msg: dict) -> None:
        """发送消息"""
        data = json.dumps(msg, ensure_ascii=False).encode("utf-8") + MESSAGE_DELIMITER
        self.writer.write(data)
        await self.writer.drain()

    async def receive(self) -> dict:
        """接收一条完整消息"""
        while True:
            delimiter_pos = self._buffer.find(MESSAGE_DELIMITER)
            if delimiter_pos != -1:
                raw_msg = self._buffer[:delimiter_pos]
                self._buffer = self._buffer[delimiter_pos + len(MESSAGE_DELIMITER):]
                return json.loads(raw_msg.decode("utf-8"))

            chunk = await self.reader.read(65536)
            if not chunk:
                raise ConnectionError("连接已关闭")
            self._buffer += chunk

    async def request(self, action: str, payload: dict = None, token: str = None) -> dict:
        """发送请求并等待响应"""
        msg = build_request(action, payload, token)
        await self.send(msg)
        return await self.receive()

    async def close(self):
        """关闭连接"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            logger.info("连接已关闭")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()
