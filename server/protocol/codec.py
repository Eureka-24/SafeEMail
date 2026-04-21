"""
消息编解码器 - JSON + \r\n 分隔，处理粘包/拆包
"""
import json
import asyncio
from typing import Optional

from shared.protocol import MESSAGE_DELIMITER, MAX_MESSAGE_SIZE


class MessageCodec:
    """消息编解码器，处理 TCP 流中的粘包/拆包问题"""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._buffer = b""

    async def read_message(self) -> Optional[dict]:
        """
        从流中读取一条完整消息
        
        Returns:
            解析后的消息字典，连接关闭时返回 None
        """
        while True:
            # 检查缓冲区中是否已有完整消息
            delimiter_pos = self._buffer.find(MESSAGE_DELIMITER)
            if delimiter_pos != -1:
                # 提取一条完整消息
                raw_msg = self._buffer[:delimiter_pos]
                self._buffer = self._buffer[delimiter_pos + len(MESSAGE_DELIMITER):]
                
                if len(raw_msg) > MAX_MESSAGE_SIZE:
                    raise ValueError(f"消息大小超过限制: {len(raw_msg)} > {MAX_MESSAGE_SIZE}")
                
                try:
                    return json.loads(raw_msg.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    raise ValueError(f"消息解码失败: {e}")

            # 从流中读取更多数据
            try:
                chunk = await self.reader.read(65536)  # 64KB 块
            except (ConnectionResetError, ConnectionAbortedError):
                return None

            if not chunk:
                # 连接关闭
                return None

            self._buffer += chunk

            # 防止缓冲区过大
            if len(self._buffer) > MAX_MESSAGE_SIZE:
                raise ValueError("缓冲区溢出：消息过大")

    async def write_message(self, msg: dict) -> None:
        """
        发送一条消息
        
        Args:
            msg: 消息字典
        """
        data = json.dumps(msg, ensure_ascii=False).encode("utf-8") + MESSAGE_DELIMITER
        self.writer.write(data)
        await self.writer.drain()

    def close(self):
        """关闭连接"""
        self.writer.close()
