"""
自动生成 CA + 服务器证书（自签名，开发环境用）
"""
import os
import sys
import datetime

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# 项目根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CERTS_DIR = os.path.join(ROOT_DIR, "certs")


def generate_key():
    """生成 RSA 2048 私钥"""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def generate_ca():
    """生成 CA 根证书"""
    key = generate_key()
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SafeEmail Dev CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, "SafeEmail Root CA"),
    ])
    
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    
    return key, cert


def generate_server_cert(ca_key, ca_cert, domain: str):
    """生成服务器证书"""
    key = generate_key()
    
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SafeEmail"),
        x509.NameAttribute(NameOID.COMMON_NAME, domain),
    ])
    
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(domain),
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress_from_string("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    
    return key, cert


def ipaddress_from_string(addr: str):
    """将字符串转换为 IP 地址对象"""
    import ipaddress
    return ipaddress.IPv4Address(addr)


def save_key(key, filepath):
    """保存私钥到文件"""
    with open(filepath, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))


def save_cert(cert, filepath):
    """保存证书到文件"""
    with open(filepath, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def main():
    os.makedirs(CERTS_DIR, exist_ok=True)
    
    print("生成 CA 根证书...")
    ca_key, ca_cert = generate_ca()
    save_key(ca_key, os.path.join(CERTS_DIR, "ca.key"))
    save_cert(ca_cert, os.path.join(CERTS_DIR, "ca.crt"))
    
    for domain in ["alpha.local", "beta.local"]:
        print(f"生成 {domain} 服务器证书...")
        srv_key, srv_cert = generate_server_cert(ca_key, ca_cert, domain)
        save_key(srv_key, os.path.join(CERTS_DIR, f"{domain}.key"))
        save_cert(srv_cert, os.path.join(CERTS_DIR, f"{domain}.crt"))
    
    print(f"证书已生成到: {CERTS_DIR}")
    print("文件列表:")
    for f in os.listdir(CERTS_DIR):
        print(f"  {f}")


if __name__ == "__main__":
    main()
