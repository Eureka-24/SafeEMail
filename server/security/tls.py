"""
TLS 上下文配置
"""
import ssl
import os


def create_server_ssl_context(cert_file: str, key_file: str, ca_file: str) -> ssl.SSLContext:
    """
    创建服务端 TLS 上下文
    
    Args:
        cert_file: 服务器证书路径
        key_file: 服务器私钥路径
        ca_file: CA 证书路径
    
    Returns:
        配置好的 SSL 上下文
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert_file, key_file)
    ctx.load_verify_locations(ca_file)
    # 可选：要求客户端证书（mTLS）
    # ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def create_client_ssl_context(ca_file: str, client_cert: str = None, client_key: str = None) -> ssl.SSLContext:
    """
    创建客户端 TLS 上下文
    
    Args:
        ca_file: CA 证书路径
        client_cert: 客户端证书路径（可选，用于 mTLS）
        client_key: 客户端私钥路径（可选）
    
    Returns:
        配置好的 SSL 上下文
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(ca_file)
    
    if client_cert and client_key:
        ctx.load_cert_chain(client_cert, client_key)
    
    # 开发环境：允许自签名证书
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    
    return ctx
