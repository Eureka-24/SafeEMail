"""
群组管理
"""
import uuid
import json
import logging

from shared.protocol import StatusCode, build_response
from server.storage.database import Database
from server.config import ServerConfig

logger = logging.getLogger(__name__)


class GroupService:
    """群组管理服务"""

    def __init__(self, db: Database, config: ServerConfig):
        self.db = db
        self.config = config
        self.domain = config.domain

    async def handle_create_group(self, msg: dict) -> dict:
        """创建/更新群组"""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        token_payload = msg.get("_token_payload", {})

        user_id = token_payload.get("sub", "")
        group_name = payload.get("group_name", "").strip()
        members = payload.get("members", [])

        if not group_name:
            return build_response(request_id, StatusCode.BAD_REQUEST, "群组名称不能为空")
        if not members:
            return build_response(request_id, StatusCode.BAD_REQUEST, "群组成员不能为空")

        # 规范化成员地址
        normalized_members = []
        for m in members:
            if "@" not in m:
                m = f"{m}@{self.domain}"
            normalized_members.append(m)

        group_id = str(uuid.uuid4())
        await self.db.execute(
            "INSERT INTO groups (group_id, owner_id, group_name, members) VALUES (?, ?, ?, ?)",
            (group_id, user_id, group_name, json.dumps(normalized_members))
        )
        await self.db.commit()

        logger.info(f"群组创建: {group_name} ({group_id}), 成员数: {len(normalized_members)}")
        return build_response(request_id, StatusCode.CREATED, "群组创建成功", {
            "group_id": group_id,
            "group_name": group_name,
            "members": normalized_members
        })

    async def handle_list_groups(self, msg: dict) -> dict:
        """列出用户的群组"""
        request_id = msg.get("request_id", "")
        token_payload = msg.get("_token_payload", {})
        user_id = token_payload.get("sub", "")

        rows = await self.db.fetchall(
            "SELECT group_id, group_name, members FROM groups WHERE owner_id = ?",
            (user_id,)
        )

        groups = []
        for row in (rows or []):
            d = dict(row)
            d["members"] = json.loads(d["members"])
            groups.append(d)

        return build_response(request_id, StatusCode.OK, "群组列表", {
            "groups": groups
        })

    async def expand_group(self, group_id: str) -> list:
        """展开群组为成员列表"""
        row = await self.db.fetchone(
            "SELECT members FROM groups WHERE group_id = ?", (group_id,)
        )
        if row:
            return json.loads(row["members"])
        return []
