"""
数据库初始化/迁移 - 建表 SQL 执行
"""
import logging

from server.storage.database import Database

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    domain TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    failed_attempts INTEGER DEFAULT 0,
    locked_until TEXT
);

-- 邮件表
CREATE TABLE IF NOT EXISTS emails (
    email_id TEXT PRIMARY KEY,
    from_user TEXT NOT NULL,
    to_users TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    category TEXT,
    keywords TEXT,
    actions TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    is_read INTEGER DEFAULT 0,
    is_spam INTEGER DEFAULT 0,
    spam_score REAL DEFAULT 0.0
);

-- 邮件-收件人关系表
CREATE TABLE IF NOT EXISTS email_recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL,
    recipient TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    is_recalled INTEGER DEFAULT 0,
    FOREIGN KEY (email_id) REFERENCES emails(email_id)
);

-- 附件表
CREATE TABLE IF NOT EXISTS attachments (
    attachment_id TEXT PRIMARY KEY,
    email_id TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    ref_count INTEGER DEFAULT 1,
    hmac_value TEXT NOT NULL,
    FOREIGN KEY (email_id) REFERENCES emails(email_id)
);

-- 群组表
CREATE TABLE IF NOT EXISTS groups (
    group_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    group_name TEXT NOT NULL,
    members TEXT NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(user_id)
);

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    user_id TEXT,
    action TEXT NOT NULL,
    ip_address TEXT,
    detail TEXT,
    level TEXT NOT NULL DEFAULT 'INFO'
);

-- Token 黑名单表
CREATE TABLE IF NOT EXISTS token_blacklist (
    jti TEXT PRIMARY KEY,
    expired_at TEXT NOT NULL
);

-- 倒排索引表
CREATE TABLE IF NOT EXISTS search_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    email_id TEXT NOT NULL,
    field TEXT NOT NULL,
    score REAL DEFAULT 1.0,
    FOREIGN KEY (email_id) REFERENCES emails(email_id)
);
CREATE INDEX IF NOT EXISTS idx_search_keyword ON search_index(keyword);

-- IP 限流记录表
CREATE TABLE IF NOT EXISTS ip_rate_limits (
    ip_address TEXT NOT NULL,
    attempt_time TEXT NOT NULL,
    action_type TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ip_rate ON ip_rate_limits(ip_address, action_type);

-- 邮件发送频率限制表
CREATE TABLE IF NOT EXISTS send_rate_limits (
    username TEXT NOT NULL,
    send_time TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_send_rate ON send_rate_limits(username, send_time);
"""


async def run_migrations(db: Database):
    """执行数据库迁移（建表）"""
    logger.info("执行数据库迁移...")
    await db.connection.executescript(SCHEMA_SQL)
    await db.commit()
    logger.info("数据库迁移完成")
