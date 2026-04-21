"""
M5 附件与存储优化测试 - 上传/下载/去重/完整性校验
"""
import asyncio
import pytest
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.protocol import Action, StatusCode
from server.main import EmailServer
from server.config import ServerConfig
from client.connection import Connection


@pytest.fixture
def attach_config():
    """附件测试配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18040
    config.data_dir = "./data/test_attachment"
    config.security.jwt_secret = "attach-test-secret-key32b"
    config.security.bcrypt_cost = 4
    config.s2s.shared_secret = "test-hmac-key-for-attachments"
    return config


@pytest.fixture
async def attach_server(attach_config):
    """启动附件测试服务器"""
    db_path = os.path.join(attach_config.data_dir, "safeemail.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    # 清理附件目录
    att_dir = os.path.join(attach_config.data_dir, "attachments")
    if os.path.exists(att_dir):
        import shutil
        shutil.rmtree(att_dir)

    server = EmailServer(attach_config)
    os.makedirs(attach_config.data_dir, exist_ok=True)
    await server._init_services()

    srv = await asyncio.start_server(
        server.handler.handle_connection,
        attach_config.host, attach_config.port
    )
    yield srv, server
    srv.close()
    await srv.wait_closed()
    await server.db.close()


@pytest.fixture
async def client(attach_config, attach_server):
    """客户端连接"""
    conn = Connection(attach_config.host, attach_config.port)
    await conn.connect()
    yield conn
    await conn.close()


async def register_and_login(client, username):
    """注册并登录"""
    await client.request(Action.REGISTER, {"username": username, "password": "TestPass123"})
    resp = await client.request(Action.LOGIN, {"username": username, "password": "TestPass123"})
    return resp["payload"]["access_token"]


class TestAttachmentUploadDownload:
    """附件上传下载测试 (M-009)"""

    @pytest.mark.asyncio
    async def test_upload_and_download(self, client):
        """TC-004: 附件上传下载完整性"""
        token = await register_and_login(client, "att_user1")
        await register_and_login(client, "att_recv1")

        # 发送一封邮件
        send_resp = await client.request(Action.SEND_MAIL, {
            "to": ["att_recv1@alpha.local"],
            "subject": "带附件邮件",
            "body": "请查看附件"
        }, token=token)
        email_id = send_resp["payload"]["email_id"]

        # 上传附件
        test_content = b"Hello, this is a test attachment file content!"
        b64_data = base64.b64encode(test_content).decode()

        upload_resp = await client.request(Action.UPLOAD_ATTACH, {
            "email_id": email_id,
            "filename": "test.txt",
            "content_type": "text/plain",
            "data": b64_data
        }, token=token)

        assert upload_resp["status"] == StatusCode.CREATED
        attachment_id = upload_resp["payload"]["attachment_id"]
        assert upload_resp["payload"]["file_size"] == len(test_content)

        # 下载附件
        download_resp = await client.request(Action.DOWNLOAD_ATTACH, {
            "attachment_id": attachment_id
        }, token=token)

        assert download_resp["status"] == StatusCode.OK
        assert download_resp["payload"]["filename"] == "test.txt"
        
        # 验证内容完整性
        downloaded_data = base64.b64decode(download_resp["payload"]["data"])
        assert downloaded_data == test_content

    @pytest.mark.asyncio
    async def test_upload_large_file_rejected(self, client):
        """超过大小限制的附件被拒绝"""
        token = await register_and_login(client, "att_large")

        send_resp = await client.request(Action.SEND_MAIL, {
            "to": ["someone@alpha.local"],
            "subject": "大文件测试",
            "body": "test"
        }, token=token)
        email_id = send_resp["payload"]["email_id"]

        # 生成超过 10MB 的数据
        large_data = b"x" * (11 * 1024 * 1024)
        b64_data = base64.b64encode(large_data).decode()

        resp = await client.request(Action.UPLOAD_ATTACH, {
            "email_id": email_id,
            "filename": "huge.bin",
            "content_type": "application/octet-stream",
            "data": b64_data
        }, token=token)

        assert resp["status"] == StatusCode.BAD_REQUEST
        assert "限制" in resp["message"]

    @pytest.mark.asyncio
    async def test_download_nonexistent(self, client):
        """下载不存在的附件"""
        token = await register_and_login(client, "att_noexist")
        resp = await client.request(Action.DOWNLOAD_ATTACH, {
            "attachment_id": "nonexistent-id"
        }, token=token)
        assert resp["status"] == StatusCode.NOT_FOUND


class TestAttachmentDedup:
    """附件去重测试 (A-003)"""

    @pytest.mark.asyncio
    async def test_dedup_same_file(self, client, attach_server):
        """TC-030: 相同文件去重验证"""
        token = await register_and_login(client, "dedup_user")

        # 发两封邮件
        send1 = await client.request(Action.SEND_MAIL, {
            "to": ["someone@alpha.local"], "subject": "邮件1", "body": "t"
        }, token=token)
        send2 = await client.request(Action.SEND_MAIL, {
            "to": ["someone@alpha.local"], "subject": "邮件2", "body": "t"
        }, token=token)
        email_id1 = send1["payload"]["email_id"]
        email_id2 = send2["payload"]["email_id"]

        # 上传相同内容到两封邮件
        same_content = b"This is the same file content for dedup test."
        b64_data = base64.b64encode(same_content).decode()

        resp1 = await client.request(Action.UPLOAD_ATTACH, {
            "email_id": email_id1, "filename": "shared.txt",
            "content_type": "text/plain", "data": b64_data
        }, token=token)
        resp2 = await client.request(Action.UPLOAD_ATTACH, {
            "email_id": email_id2, "filename": "shared_copy.txt",
            "content_type": "text/plain", "data": b64_data
        }, token=token)

        assert resp1["status"] == StatusCode.CREATED
        assert resp2["status"] == StatusCode.CREATED

        # 两个附件 ID 不同，但哈希相同
        assert resp1["payload"]["attachment_id"] != resp2["payload"]["attachment_id"]
        assert resp1["payload"]["file_hash"] == resp2["payload"]["file_hash"]

        # 两个都可以正常下载
        dl1 = await client.request(Action.DOWNLOAD_ATTACH, {
            "attachment_id": resp1["payload"]["attachment_id"]
        }, token=token)
        dl2 = await client.request(Action.DOWNLOAD_ATTACH, {
            "attachment_id": resp2["payload"]["attachment_id"]
        }, token=token)
        assert dl1["status"] == StatusCode.OK
        assert dl2["status"] == StatusCode.OK
        assert base64.b64decode(dl1["payload"]["data"]) == same_content
        assert base64.b64decode(dl2["payload"]["data"]) == same_content


class TestIntegrity:
    """完整性校验测试"""

    @pytest.mark.asyncio
    async def test_tamper_detection(self, client, attach_server, attach_config):
        """TC-032: 篡改检测"""
        _, server = attach_server
        token = await register_and_login(client, "tamper_user")

        send_resp = await client.request(Action.SEND_MAIL, {
            "to": ["someone@alpha.local"], "subject": "篡改测试", "body": "t"
        }, token=token)
        email_id = send_resp["payload"]["email_id"]

        # 上传附件
        original = b"Original content for integrity test"
        b64_data = base64.b64encode(original).decode()
        upload_resp = await client.request(Action.UPLOAD_ATTACH, {
            "email_id": email_id, "filename": "integrity.txt",
            "content_type": "text/plain", "data": b64_data
        }, token=token)
        attachment_id = upload_resp["payload"]["attachment_id"]

        # 直接篡改存储的文件
        row = await server.db.fetchone(
            "SELECT storage_path FROM attachments WHERE attachment_id = ?",
            (attachment_id,)
        )
        storage_path = dict(row)["storage_path"]
        with open(storage_path, "wb") as f:
            f.write(b"TAMPERED CONTENT!!!")

        # 尝试下载，应该检测到篡改
        dl_resp = await client.request(Action.DOWNLOAD_ATTACH, {
            "attachment_id": attachment_id
        }, token=token)
        assert dl_resp["status"] == StatusCode.NOT_FOUND
        assert "篡改" in dl_resp["message"] or "完整性" in dl_resp["message"]


class TestDedupDeletion:
    """去重后删除引用计数测试 (TC-031)"""

    @pytest.mark.asyncio
    async def test_delete_dedup_ref_count(self, client, attach_server, attach_config):
        """TC-031: 去重后删除一个附件，另一个仍可访问，文件不被物理删除"""
        _, server = attach_server
        token = await register_and_login(client, "dedup_del_user")

        # 发两封邮件
        send1 = await client.request(Action.SEND_MAIL, {
            "to": ["someone@alpha.local"], "subject": "去重删1", "body": "t"
        }, token=token)
        send2 = await client.request(Action.SEND_MAIL, {
            "to": ["someone@alpha.local"], "subject": "去重删2", "body": "t"
        }, token=token)
        eid1 = send1["payload"]["email_id"]
        eid2 = send2["payload"]["email_id"]

        # 上传相同内容到两封邮件
        content = b"Dedup deletion test content"
        b64 = base64.b64encode(content).decode()
        r1 = await client.request(Action.UPLOAD_ATTACH, {
            "email_id": eid1, "filename": "dup1.txt",
            "content_type": "text/plain", "data": b64
        }, token=token)
        r2 = await client.request(Action.UPLOAD_ATTACH, {
            "email_id": eid2, "filename": "dup2.txt",
            "content_type": "text/plain", "data": b64
        }, token=token)
        assert r1["status"] == StatusCode.CREATED
        assert r2["status"] == StatusCode.CREATED
        aid1 = r1["payload"]["attachment_id"]
        aid2 = r2["payload"]["attachment_id"]

        # 删除第一个附件
        ok, msg = await server.attachment_service.delete(aid1)
        assert ok

        # 第一个不可下载
        dl1 = await client.request(Action.DOWNLOAD_ATTACH, {
            "attachment_id": aid1
        }, token=token)
        assert dl1["status"] == StatusCode.NOT_FOUND

        # 第二个仍可下载（文件未被物理删除）
        dl2 = await client.request(Action.DOWNLOAD_ATTACH, {
            "attachment_id": aid2
        }, token=token)
        assert dl2["status"] == StatusCode.OK
        assert base64.b64decode(dl2["payload"]["data"]) == content

    @pytest.mark.asyncio
    async def test_delete_last_ref_physical_removal(self, client, attach_server, attach_config):
        """TC-031b: 删除最后一个引用后物理文件被删除"""
        _, server = attach_server
        token = await register_and_login(client, "del_last_user")

        send = await client.request(Action.SEND_MAIL, {
            "to": ["someone@alpha.local"], "subject": "单独删除", "body": "t"
        }, token=token)
        eid = send["payload"]["email_id"]

        content = b"Unique content for physical delete test"
        b64 = base64.b64encode(content).decode()
        r = await client.request(Action.UPLOAD_ATTACH, {
            "email_id": eid, "filename": "unique.txt",
            "content_type": "text/plain", "data": b64
        }, token=token)
        aid = r["payload"]["attachment_id"]

        # 获取存储路径
        row = await server.db.fetchone(
            "SELECT storage_path FROM attachments WHERE attachment_id = ?",
            (aid,)
        )
        storage_path = dict(row)["storage_path"]
        assert os.path.exists(storage_path)

        # 删除
        ok, msg = await server.attachment_service.delete(aid)
        assert ok

        # 物理文件应被删除
        assert not os.path.exists(storage_path)
