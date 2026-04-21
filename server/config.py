"""
服务端配置管理 - YAML 配置加载
"""
import os
import yaml
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TLSConfig:
    cert_file: str = ""
    key_file: str = ""
    ca_file: str = ""


@dataclass
class PeerConfig:
    domain: str = ""
    host: str = "127.0.0.1"
    port: int = 8002


@dataclass
class S2SConfig:
    peers: List[PeerConfig] = field(default_factory=list)
    shared_secret: str = "s2s-shared-secret-key"


@dataclass
class SecurityConfig:
    jwt_secret: str = "default-jwt-secret"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7
    bcrypt_cost: int = 12
    max_login_attempts_ip: int = 5
    ip_lockout_minutes: int = 15
    max_login_attempts_account: int = 10
    account_lockout_minutes: int = 30
    max_send_per_minute: int = 10
    max_send_per_hour: int = 60
    max_connections_per_ip: int = 50
    max_message_size_mb: int = 15
    recall_window_minutes: int = 5


@dataclass
class IntelligenceConfig:
    categories: List[str] = field(default_factory=lambda: ["工作", "通知", "广告/营销", "社交", "其他"])
    keyword_top_n: int = 5
    fuzzy_max_distance: int = 2
    ngram_size: int = 3


@dataclass
class ServerConfig:
    domain: str = "alpha.local"
    host: str = "127.0.0.1"
    port: int = 8001
    data_dir: str = "./data/alpha.local"
    tls: TLSConfig = field(default_factory=TLSConfig)
    s2s: S2SConfig = field(default_factory=S2SConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    intelligence: IntelligenceConfig = field(default_factory=IntelligenceConfig)


def load_config(config_path: str) -> ServerConfig:
    """从 YAML 文件加载配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    config = ServerConfig()

    # 服务器基本配置
    server_raw = raw.get("server", {})
    config.domain = server_raw.get("domain", config.domain)
    config.host = server_raw.get("host", config.host)
    config.port = server_raw.get("port", config.port)
    config.data_dir = server_raw.get("data_dir", config.data_dir)

    # TLS 配置
    tls_raw = raw.get("tls", {})
    config.tls.cert_file = tls_raw.get("cert_file", "")
    config.tls.key_file = tls_raw.get("key_file", "")
    config.tls.ca_file = tls_raw.get("ca_file", "")

    # S2S 配置
    s2s_raw = raw.get("s2s", {})
    config.s2s.shared_secret = s2s_raw.get("shared_secret", config.s2s.shared_secret)
    peers_raw = s2s_raw.get("peers", [])
    config.s2s.peers = [
        PeerConfig(
            domain=p.get("domain", ""),
            host=p.get("host", "127.0.0.1"),
            port=p.get("port", 8002)
        )
        for p in peers_raw
    ]

    # 安全配置
    sec_raw = raw.get("security", {})
    for key in vars(config.security):
        if key in sec_raw:
            setattr(config.security, key, sec_raw[key])

    # 智能引擎配置
    intel_raw = raw.get("intelligence", {})
    for key in vars(config.intelligence):
        if key in intel_raw:
            setattr(config.intelligence, key, intel_raw[key])

    return config
