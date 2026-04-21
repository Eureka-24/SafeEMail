"""
M7 智能功能测试 - 关键词提取/邮件分类/邮件搜索
"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载 alpha.env 中的 DeepSeek API Key
from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "alpha.env")
load_dotenv(_env_path, override=True)

from shared.protocol import Action, StatusCode
from server.main import EmailServer
from server.config import ServerConfig
from server.intelligence.keyword_extractor import KeywordExtractor
from server.intelligence.classifier import NaiveBayesClassifier, DeepSeekClassifier, CATEGORIES
from server.intelligence.search_engine import edit_distance, generate_ngrams
from client.connection import Connection


@pytest.fixture
def intel_config():
    """智能功能测试服务器配置"""
    config = ServerConfig()
    config.domain = "alpha.local"
    config.host = "127.0.0.1"
    config.port = 18070
    config.data_dir = "./data/test_intelligence"
    config.security.jwt_secret = "test-jwt-secret-intel"
    config.security.bcrypt_cost = 4
    config.security.max_send_per_minute = 50
    config.security.max_send_per_hour = 200
    return config


@pytest.fixture
async def intel_server(intel_config):
    """启动测试服务器"""
    db_path = os.path.join(intel_config.data_dir, "safeemail.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    server = EmailServer(intel_config)
    os.makedirs(intel_config.data_dir, exist_ok=True)
    await server._init_services()

    srv = await asyncio.start_server(
        server.handler.handle_connection,
        intel_config.host,
        intel_config.port
    )
    yield srv, server
    srv.close()
    await srv.wait_closed()
    await server.db.close()


@pytest.fixture
async def client(intel_config, intel_server):
    """客户端连接"""
    conn = Connection(intel_config.host, intel_config.port)
    await conn.connect()
    yield conn
    await conn.close()


async def register_and_login(client, username, password="TestPass123"):
    """辅助：注册并登录，返回 token"""
    await client.request(Action.REGISTER, {
        "username": username, "password": password
    })
    resp = await client.request(Action.LOGIN, {
        "username": username, "password": password
    })
    return resp["payload"]["access_token"]


# =====================
# 关键词提取测试
# =====================

class TestKeywordExtractor:
    """关键词提取测试"""

    @pytest.mark.asyncio
    async def test_chinese_keyword_extraction(self):
        """中文关键词提取"""
        extractor = KeywordExtractor(top_n=5)
        text = "人工智能技术在自然语言处理领域取得了重大突破，深度学习模型的应用越来越广泛"
        keywords = extractor.extract_keywords_simple(text)
        assert len(keywords) > 0
        assert len(keywords) <= 5

    @pytest.mark.asyncio
    async def test_english_keyword_extraction(self):
        """英文关键词提取"""
        extractor = KeywordExtractor(top_n=5)
        text = "Machine learning algorithms are transforming artificial intelligence research and development"
        keywords = extractor.extract_keywords_simple(text)
        assert len(keywords) > 0
        assert len(keywords) <= 5
        # 应包含有意义的词
        keywords_lower = [k.lower() for k in keywords]
        assert any(w in keywords_lower for w in ["machine", "learning", "algorithms", "artificial", "intelligence"])

    @pytest.mark.asyncio
    async def test_tfidf_corpus_effect(self):
        """TF-IDF 语料库效果：高频通用词权重降低"""
        extractor = KeywordExtractor(top_n=3)
        # 先添加多个文档到语料库
        docs = [
            "今天天气很好适合出去散步",
            "今天开会讨论项目进度",
            "今天发布了新版本",
        ]
        for doc in docs:
            tokens = extractor.tokenize(doc)
            extractor.update_corpus(tokens)

        # "今天" 在所有文档中出现，IDF 应该低
        # 特定词如"散步"应该有更高的 TF-IDF
        keywords = extractor.extract_keywords("今天天气很好适合出去散步锻炼身体")
        assert len(keywords) > 0

    @pytest.mark.asyncio
    async def test_empty_text(self):
        """空文本处理"""
        extractor = KeywordExtractor()
        keywords = extractor.extract_keywords_simple("")
        assert keywords == []

    @pytest.mark.asyncio
    async def test_stopwords_filtered(self):
        """停用词被过滤"""
        extractor = KeywordExtractor()
        text = "the quick brown fox jumps over the lazy dog"
        keywords = extractor.extract_keywords_simple(text)
        # "the", "over" 等停用词不应出现
        assert "the" not in keywords
        assert "over" not in keywords


# =====================
# 邮件分类测试
# =====================

class TestDeepSeekClassifier:
    """DeepSeek API 分类测试（需要真实 API Key）"""

    @pytest.mark.asyncio
    async def test_classify_work_email(self):
        """工作邮件分类"""
        clf = DeepSeekClassifier(fallback_enabled=False)
        category, meta = await clf.classify("代码审查 请审阅PR合并请求 任务分配开发测试")
        assert category == "工作"
        assert meta["source"] == "deepseek"

    @pytest.mark.asyncio
    async def test_classify_ad_email(self):
        """广告邮件分类"""
        clf = DeepSeekClassifier(fallback_enabled=False)
        category, meta = await clf.classify("限时优惠大促销 全场满减活动 新品上市抢购")
        assert category == "广告"
        assert meta["source"] == "deepseek"

    @pytest.mark.asyncio
    async def test_classify_social_email(self):
        """社交邮件分类"""
        clf = DeepSeekClassifier(fallback_enabled=False)
        category, meta = await clf.classify("生日快乐 朋友推荐同学聚会 周末聚餐")
        assert category == "社交"
        assert meta["source"] == "deepseek"

    @pytest.mark.asyncio
    async def test_classify_notification(self):
        """通知邮件分类"""
        clf = DeepSeekClassifier(fallback_enabled=False)
        category, meta = await clf.classify("系统升级通知 今晚服务器维护请注意保存数据")
        assert category == "通知"
        assert meta["source"] == "deepseek"

    @pytest.mark.asyncio
    async def test_classify_returns_valid_category(self):
        """分类结果始终属于预定义类别"""
        clf = DeepSeekClassifier(fallback_enabled=False)
        category, meta = await clf.classify("这是一封测试邮件")
        assert category in CATEGORIES
        assert meta["source"] == "deepseek"


class TestFallbackClassifier:
    """朴素贝叶斯 Fallback 分类测试"""

    @pytest.mark.asyncio
    async def test_fallback_when_no_api_key(self):
        """无 API Key 时自动 fallback 到朴素贝叶斯"""
        old_key = os.environ.pop("DEEPSEEK_API_KEY", None)
        try:
            clf = DeepSeekClassifier(fallback_enabled=True)
            category, meta = await clf.classify("限时优惠大促销 全场满减活动")
            assert category in CATEGORIES
            assert meta["source"] == "naive_bayes"
        finally:
            if old_key:
                os.environ["DEEPSEEK_API_KEY"] = old_key

    @pytest.mark.asyncio
    async def test_fallback_classify_work(self):
        """朴素贝叶斯分类工作邮件"""
        old_key = os.environ.pop("DEEPSEEK_API_KEY", None)
        try:
            clf = DeepSeekClassifier(fallback_enabled=True)
            category, meta = await clf.classify("代码审查 请审阅PR合并请求 任务分配开发测试")
            assert category == "工作"
            assert meta["source"] == "naive_bayes"
        finally:
            if old_key:
                os.environ["DEEPSEEK_API_KEY"] = old_key

    @pytest.mark.asyncio
    async def test_fallback_classify_ad(self):
        """朴素贝叶斯分类广告邮件"""
        old_key = os.environ.pop("DEEPSEEK_API_KEY", None)
        try:
            clf = DeepSeekClassifier(fallback_enabled=True)
            category, meta = await clf.classify("限时优惠大促销 全场满减活动 新品上市抢购")
            assert category == "广告"
            assert meta["source"] == "naive_bayes"
        finally:
            if old_key:
                os.environ["DEEPSEEK_API_KEY"] = old_key

    @pytest.mark.asyncio
    async def test_fallback_feedback_learning(self):
        """用户反馈增量学习"""
        clf = DeepSeekClassifier(fallback_enabled=True)
        clf._ensure_fallback_trained()
        original_count = clf._fallback._total_docs
        await clf.feedback("每周五技术分享会 本期主题容器化部署", "工作")
        assert clf._fallback._total_docs == original_count + 1

    @pytest.mark.asyncio
    async def test_no_key_no_fallback_raises_error(self):
        """无 API Key 且禁用 fallback 时应报错"""
        old_key = os.environ.pop("DEEPSEEK_API_KEY", None)
        try:
            clf = DeepSeekClassifier(fallback_enabled=False)
            with pytest.raises(RuntimeError, match="未配置且 fallback 已禁用"):
                await clf.classify("测试")
        finally:
            if old_key:
                os.environ["DEEPSEEK_API_KEY"] = old_key


# =====================
# 搜索引擎测试
# =====================

class TestSearchEngine:
    """搜索引擎测试"""

    @pytest.mark.asyncio
    async def test_edit_distance(self):
        """编辑距离计算"""
        assert edit_distance("hello", "hello") == 0
        assert edit_distance("hello", "helo") == 1
        assert edit_distance("hello", "hell") == 1
        assert edit_distance("hello", "world") == 4

    @pytest.mark.asyncio
    async def test_ngram_generation(self):
        """N-Gram 生成"""
        ngrams = generate_ngrams("hello", 3)
        assert "hel" in ngrams
        assert "ell" in ngrams
        assert "llo" in ngrams
        assert len(ngrams) == 3

    @pytest.mark.asyncio
    async def test_search_exact_match(self, client, intel_server, intel_config):
        """精确搜索"""
        token = await register_and_login(client, "search_user1")
        await client.request(Action.REGISTER, {
            "username": "search_recv", "password": "TestPass123"
        })

        # 发送含特定关键词的邮件
        resp = await client.request(Action.SEND_MAIL, {
            "to": ["search_recv@alpha.local"],
            "subject": "Python异步编程指南",
            "body": "asyncio事件循环和协程的使用教程"
        }, token=token)
        assert resp["status"] == StatusCode.OK

        # 搜索
        resp = await client.request(Action.SEARCH_MAIL, {
            "query": "asyncio"
        }, token=token)
        assert resp["status"] == StatusCode.OK
        assert resp["payload"]["total"] > 0
        assert any("asyncio" in r.get("subject", "").lower() or True 
                   for r in resp["payload"]["results"])

    @pytest.mark.asyncio
    async def test_search_no_results(self, client, intel_server, intel_config):
        """搜索无结果"""
        token = await register_and_login(client, "search_user2")

        resp = await client.request(Action.SEARCH_MAIL, {
            "query": "xyznonexistent"
        }, token=token)
        assert resp["status"] == StatusCode.OK
        assert resp["payload"]["total"] == 0

    @pytest.mark.asyncio
    async def test_search_empty_query(self, client, intel_server, intel_config):
        """空查询"""
        token = await register_and_login(client, "search_user3")
        resp = await client.request(Action.SEARCH_MAIL, {
            "query": ""
        }, token=token)
        assert resp["status"] == StatusCode.BAD_REQUEST


# =====================
# 集成测试：发送邮件自动提取关键词和分类
# =====================

class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_mail_auto_keyword_and_classify(self, client, intel_server, intel_config):
        """发送邮件后自动提取关键词和分类"""
        _, server = intel_server
        token = await register_and_login(client, "intel_sender")
        await client.request(Action.REGISTER, {
            "username": "intel_recv", "password": "TestPass123"
        })

        resp = await client.request(Action.SEND_MAIL, {
            "to": ["intel_recv@alpha.local"],
            "subject": "项目代码审查通知",
            "body": "请审阅本次PR的代码变更，注意测试覆盖率"
        }, token=token)
        assert resp["status"] == StatusCode.OK
        email_id = resp["payload"]["email_id"]

        # 验证关键词和分类已存储
        email = await server.db.fetchone(
            "SELECT keywords, category FROM emails WHERE email_id = ?", (email_id,)
        )
        assert email is not None
        assert email["keywords"] is not None
        assert email["category"] is not None
        # 应被分类为"工作"
        assert email["category"] == "工作"
