"""
共享协议模块 - 协议常量、Action 枚举、消息构造工具
"""
import json
import uuid
from enum import Enum
from typing import Any, Optional


# 协议版本
PROTOCOL_VERSION = "1.0"

# 消息分隔符
MESSAGE_DELIMITER = b"\r\n"

# 最大消息大小 (15MB)
MAX_MESSAGE_SIZE = 15 * 1024 * 1024

# 消息类型
class MessageType(str, Enum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    S2S_REQUEST = "S2S_REQUEST"
    S2S_RESPONSE = "S2S_RESPONSE"


# Action 枚举
class Action(str, Enum):
    # 系统
    PING = "PING"
    PONG = "PONG"

    # 认证
    REGISTER = "REGISTER"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    REFRESH = "REFRESH"

    # 邮件
    SEND_MAIL = "SEND_MAIL"
    LIST_INBOX = "LIST_INBOX"
    READ_MAIL = "READ_MAIL"
    LIST_SENT = "LIST_SENT"
    SAVE_DRAFT = "SAVE_DRAFT"
    LIST_DRAFTS = "LIST_DRAFTS"
    RECALL_MAIL = "RECALL_MAIL"
    SEARCH_MAIL = "SEARCH_MAIL"
    QUICK_REPLY = "QUICK_REPLY"

    # 群组
    CREATE_GROUP = "CREATE_GROUP"
    LIST_GROUPS = "LIST_GROUPS"

    # 附件
    UPLOAD_ATTACH = "UPLOAD_ATTACH"
    DOWNLOAD_ATTACH = "DOWNLOAD_ATTACH"

    # 快捷操作
    EXEC_ACTION = "EXEC_ACTION"

    # S2S 中继
    S2S_DELIVER = "S2S_DELIVER"
    S2S_RECALL = "S2S_RECALL"


# 状态码
class StatusCode:
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    TOO_MANY_REQUESTS = 429
    INTERNAL_ERROR = 500


def build_request(action: str, payload: dict = None, token: str = None) -> dict:
    """构造请求消息"""
    return {
        "version": PROTOCOL_VERSION,
        "type": MessageType.REQUEST,
        "action": action,
        "request_id": str(uuid.uuid4()),
        "token": token,
        "payload": payload or {}
    }


def build_response(request_id: str, status: int, message: str = "", payload: dict = None) -> dict:
    """构造响应消息"""
    return {
        "version": PROTOCOL_VERSION,
        "type": MessageType.RESPONSE,
        "request_id": request_id,
        "status": status,
        "message": message,
        "payload": payload or {}
    }


def build_s2s_request(action: str, server_id: str, signature: str, payload: dict = None) -> dict:
    """构造 S2S 请求消息"""
    return {
        "version": PROTOCOL_VERSION,
        "type": MessageType.S2S_REQUEST,
        "action": action,
        "server_id": server_id,
        "signature": signature,
        "payload": payload or {}
    }


def encode_message(msg: dict) -> bytes:
    """将消息字典编码为传输字节"""
    return json.dumps(msg, ensure_ascii=False).encode("utf-8") + MESSAGE_DELIMITER


def decode_message(data: bytes) -> dict:
    """将字节数据解码为消息字典"""
    return json.loads(data.decode("utf-8").strip())
