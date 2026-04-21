"""
密码策略 - 密码强度校验 + bcrypt 哈希
"""
import re
import bcrypt


def validate_password(password: str) -> tuple[bool, str]:
    """
    校验密码强度
    
    规则：≥8位，包含大写+小写+数字
    
    Returns:
        (是否合规, 错误消息)
    """
    if len(password) < 8:
        return False, "密码长度不能少于8位"
    
    if not re.search(r"[A-Z]", password):
        return False, "密码必须包含至少一个大写字母"
    
    if not re.search(r"[a-z]", password):
        return False, "密码必须包含至少一个小写字母"
    
    if not re.search(r"\d", password):
        return False, "密码必须包含至少一个数字"
    
    return True, ""


def hash_password(password: str, cost: int = 12) -> str:
    """
    使用 bcrypt 对密码进行哈希
    
    Args:
        password: 明文密码
        cost: bcrypt cost factor
    
    Returns:
        bcrypt 哈希字符串
    """
    salt = bcrypt.gensalt(rounds=cost)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码是否匹配哈希
    
    Args:
        password: 明文密码
        password_hash: bcrypt 哈希
    
    Returns:
        是否匹配
    """
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
