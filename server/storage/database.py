"""
SQLite 数据库管理 - 连接管理，WAL 模式
"""
import os
import aiosqlite
import logging

logger = logging.getLogger(__name__)


class Database:
    """SQLite 异步数据库管理器"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, "safeemail.db")
        self._db: aiosqlite.Connection = None

    async def connect(self):
        """连接数据库并启用 WAL 模式"""
        os.makedirs(self.data_dir, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        
        # 启用 WAL 模式
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.commit()
        
        logger.info(f"数据库已连接: {self.db_path}")

    async def close(self):
        """关闭数据库连接"""
        if self._db:
            await self._db.close()
            logger.info("数据库连接已关闭")

    @property
    def connection(self) -> aiosqlite.Connection:
        """获取数据库连接"""
        return self._db

    async def execute(self, sql: str, params=None):
        """执行 SQL"""
        if params:
            return await self._db.execute(sql, params)
        return await self._db.execute(sql)

    async def executemany(self, sql: str, params_list):
        """批量执行 SQL"""
        return await self._db.executemany(sql, params_list)

    async def fetchone(self, sql: str, params=None):
        """查询单行"""
        cursor = await self.execute(sql, params)
        return await cursor.fetchone()

    async def fetchall(self, sql: str, params=None):
        """查询多行"""
        cursor = await self.execute(sql, params)
        return await cursor.fetchall()

    async def commit(self):
        """提交事务"""
        await self._db.commit()
