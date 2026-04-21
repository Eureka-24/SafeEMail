"""
共享加密工具模块 - HMAC 工具函数
"""
import hmac
import hashlib
from typing import Union


def compute_hmac(key: Union[str, bytes], message: Union[str, bytes]) -> str:
    """
    计算 HMAC-SHA256 签名
    
    Args:
        key: 密钥（字符串或字节）
        message: 待签名消息（字符串或字节）
    
    Returns:
        十六进制 HMAC 签名字符串
    """
    if isinstance(key, str):
        key = key.encode("utf-8")
    if isinstance(message, str):
        message = message.encode("utf-8")
    
    return hmac.HMAC(key, message, hashlib.sha256).hexdigest()


def verify_hmac(key: Union[str, bytes], message: Union[str, bytes], signature: str) -> bool:
    """
    验证 HMAC-SHA256 签名
    
    Args:
        key: 密钥
        message: 原始消息
        signature: 待验证的签名
    
    Returns:
        签名是否有效
    """
    expected = compute_hmac(key, message)
    return hmac.compare_digest(expected, signature)


def compute_sha256(data: bytes) -> str:
    """
    计算 SHA-256 哈希
    
    Args:
        data: 待哈希数据
    
    Returns:
        十六进制哈希字符串
    """
    return hashlib.sha256(data).hexdigest()
