"""
附件存储与去重 - SHA-256 哈希寻址存储 + HMAC 完整性校验
"""
import os
import uuid
import base64
import logging
from typing import Optional, Tuple

from shared.crypto import compute_sha256, compute_hmac
from server.storage.database import Database
from server.config import ServerConfig

logger = logging.getLogger(__name__)

# 最大附件大小 10MB
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024


class AttachmentService:
    """附件服务"""

    def __init__(self, db: Database, config: ServerConfig):
        self.db = db
        self.config = config
        self.domain = config.domain
        self.storage_root = os.path.join(config.data_dir, "attachments")
        self.hmac_key = config.s2s.shared_secret  # 复用共享密钥作为 HMAC 密钥
        os.makedirs(self.storage_root, exist_ok=True)

    def _get_storage_path(self, file_hash: str) -> str:
        """根据哈希生成存储路径: {hash[0:2]}/{hash[2:4]}/{full_hash}"""
        return os.path.join(
            self.storage_root,
            file_hash[0:2],
            file_hash[2:4],
            file_hash
        )

    async def upload(self, email_id: str, filename: str, content_type: str, 
                     base64_data: str) -> Tuple[bool, str, dict]:
        """
        上传附件
        
        Args:
            email_id: 关联邮件ID
            filename: 文件名
            content_type: MIME 类型
            base64_data: Base64 编码的文件内容
            
        Returns:
            (成功, 消息/attachment_id, 附件信息)
        """
        # 解码 Base64
        try:
            file_data = base64.b64decode(base64_data)
        except Exception:
            return False, "Base64 解码失败", {}

        # 检查大小
        if len(file_data) > MAX_ATTACHMENT_SIZE:
            return False, f"附件大小超过限制({MAX_ATTACHMENT_SIZE // 1024 // 1024}MB)", {}

        # 计算 SHA-256 哈希
        file_hash = compute_sha256(file_data)

        # 检查去重
        existing = await self.db.fetchone(
            "SELECT attachment_id, storage_path, ref_count FROM attachments WHERE file_hash = ? AND email_id != ?",
            (file_hash, email_id)
        )

        storage_path = self._get_storage_path(file_hash)
        attachment_id = str(uuid.uuid4())

        if existing:
            # 去重：引用计数 +1，复用存储路径
            existing_dict = dict(existing)
            await self.db.execute(
                "UPDATE attachments SET ref_count = ref_count + 1 WHERE file_hash = ?",
                (file_hash,)
            )
            # 为新附件创建记录（关联到新邮件）
            hmac_value = compute_hmac(self.hmac_key, file_data)
            await self.db.execute(
                """INSERT INTO attachments 
                   (attachment_id, email_id, file_hash, filename, content_type, file_size, storage_path, ref_count, hmac_value)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (attachment_id, email_id, file_hash, filename, content_type, 
                 len(file_data), existing_dict["storage_path"], hmac_value)
            )
            await self.db.commit()
            
            logger.info(f"附件去重复用: {file_hash}, ref_count+1")
        else:
            # 新文件：写入存储
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            with open(storage_path, "wb") as f:
                f.write(file_data)

            # 计算 HMAC
            hmac_value = compute_hmac(self.hmac_key, file_data)

            # 写入数据库
            await self.db.execute(
                """INSERT INTO attachments 
                   (attachment_id, email_id, file_hash, filename, content_type, file_size, storage_path, ref_count, hmac_value)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (attachment_id, email_id, file_hash, filename, content_type,
                 len(file_data), storage_path, hmac_value)
            )
            await self.db.commit()
            
            logger.info(f"附件上传: {filename} ({len(file_data)} bytes), hash={file_hash[:16]}...")

        return True, attachment_id, {
            "attachment_id": attachment_id,
            "filename": filename,
            "file_size": len(file_data),
            "file_hash": file_hash
        }

    async def download(self, attachment_id: str) -> Tuple[bool, str, dict]:
        """
        下载附件（含完整性校验）
        
        Returns:
            (成功, 消息, {filename, content_type, data_base64})
        """
        row = await self.db.fetchone(
            "SELECT * FROM attachments WHERE attachment_id = ?", (attachment_id,)
        )
        if not row:
            return False, "附件不存在", {}

        att = dict(row)
        storage_path = att["storage_path"]

        if not os.path.exists(storage_path):
            return False, "附件文件丢失", {}

        # 读取文件
        with open(storage_path, "rb") as f:
            file_data = f.read()

        # HMAC 完整性校验
        computed_hmac = compute_hmac(self.hmac_key, file_data)
        if computed_hmac != att["hmac_value"]:
            logger.error(f"附件完整性校验失败: {attachment_id}")
            return False, "附件完整性校验失败，文件可能被篡改", {}

        # 返回 Base64 编码
        data_base64 = base64.b64encode(file_data).decode("utf-8")
        
        return True, "下载成功", {
            "attachment_id": attachment_id,
            "filename": att["filename"],
            "content_type": att["content_type"],
            "file_size": att["file_size"],
            "data": data_base64
        }

    async def delete(self, attachment_id: str) -> Tuple[bool, str]:
        """
        删除附件（引用计数递减，归零物理删除）
        
        Returns:
            (成功, 消息)
        """
        row = await self.db.fetchone(
            "SELECT file_hash, storage_path, ref_count FROM attachments WHERE attachment_id = ?",
            (attachment_id,)
        )
        if not row:
            return False, "附件不存在"

        att = dict(row)
        file_hash = att["file_hash"]

        # 删除当前记录
        await self.db.execute(
            "DELETE FROM attachments WHERE attachment_id = ?", (attachment_id,)
        )

        # 检查同哈希的其他引用
        remaining = await self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM attachments WHERE file_hash = ?", (file_hash,)
        )
        remaining_count = remaining["cnt"] if remaining else 0

        if remaining_count == 0:
            # 无引用，物理删除文件
            storage_path = att["storage_path"]
            if os.path.exists(storage_path):
                os.remove(storage_path)
                logger.info(f"附件物理删除: {file_hash}")

        await self.db.commit()
        return True, "删除成功"

    async def get_storage_stats(self) -> dict:
        """获取存储空间节省统计"""
        # 总附件数
        total_row = await self.db.fetchone("SELECT COUNT(*) as cnt FROM attachments")
        total_count = total_row["cnt"] if total_row else 0

        # 唯一文件数
        unique_row = await self.db.fetchone("SELECT COUNT(DISTINCT file_hash) as cnt FROM attachments")
        unique_count = unique_row["cnt"] if unique_row else 0

        # 总大小 vs 实际存储大小
        total_size_row = await self.db.fetchone("SELECT SUM(file_size) as total FROM attachments")
        total_size = total_size_row["total"] if total_size_row and total_size_row["total"] else 0

        # 实际文件大小（去重后）
        actual_row = await self.db.fetchone(
            "SELECT SUM(file_size) as total FROM (SELECT DISTINCT file_hash, file_size FROM attachments)"
        )
        actual_size = actual_row["total"] if actual_row and actual_row["total"] else 0

        saved = total_size - actual_size

        return {
            "total_attachments": total_count,
            "unique_files": unique_count,
            "total_logical_size": total_size,
            "actual_storage_size": actual_size,
            "space_saved": saved
        }

