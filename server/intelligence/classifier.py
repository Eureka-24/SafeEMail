"""
邮件分类 - DeepSeek API (OpenAI 兼容接口) + 朴素贝叶斯 Fallback
"""
import os
import math
import logging
import asyncio
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

# 预定义类别
CATEGORIES = ["工作", "通知", "广告", "社交", "其他"]

# DeepSeek API 配置
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# 分类 Prompt 模板
CLASSIFICATION_PROMPT = """你是一个邮件分类助手。请根据邮件内容，将其分类到以下类别之一：
- 工作：项目、任务、会议、代码、部署等工作相关
- 通知：系统通知、密码过期、账单、公告、服务变更等
- 广告：促销、优惠、打折、新品、领取等营销内容
- 社交：聚会、生日、祝福、旅行分享、朋友等社交互动
- 其他：不属于以上任何类别

请只回复类别名称（工作/通知/广告/社交/其他），不要有其他内容。

邮件内容：
{text}"""


class DeepSeekClassifier:
    """
    邮件分类器 - 支持 DeepSeek API 主分类 + 朴素贝叶斯 Fallback

    Args:
        categories: 分类类别列表
        api_key: DeepSeek API Key（可选，默认从环境变量读取）
        fallback_enabled: 是否启用朴素贝叶斯 fallback（默认 True）
    """

    def __init__(self, categories: List[str] = None, api_key: str = None,
                 fallback_enabled: bool = True):
        self.categories = categories or CATEGORIES
        self._client = None
        self._explicit_api_key = api_key
        self.fallback_enabled = fallback_enabled
        # Fallback 分类器（延迟训练）
        self._fallback = NaiveBayesClassifier(categories=self.categories)
        self._fallback_trained = False

    def _get_api_key(self) -> str:
        """获取 API Key（优先使用显式传入的，否则从环境变量实时读取）"""
        if self._explicit_api_key:
            return self._explicit_api_key
        return os.environ.get("DEEPSEEK_API_KEY", "")

    def _get_client(self):
        """延迟初始化 OpenAI 客户端（同步客户端，避免 anyio 兼容问题）"""
        api_key = self._get_api_key()
        if not api_key:
            return None
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=api_key,
                base_url=DEEPSEEK_BASE_URL
            )
        return self._client

    def _ensure_fallback_trained(self, tokenizer=None):
        """确保 fallback 分类器已训练"""
        if not self._fallback_trained:
            self._fallback.train_with_seeds(tokenizer)
            self._fallback_trained = True

    async def classify(self, text: str, tokenizer=None) -> Tuple[str, Dict]:
        """
        对文本进行分类。
        优先使用 DeepSeek API；若失败且 fallback_enabled=True，降级到朴素贝叶斯。

        Args:
            text: 待分类文本
            tokenizer: 分词函数（fallback 时使用）

        Returns:
            (预测类别, 元数据信息 {source, ...})
        """
        # 1. 尝试 DeepSeek API
        client = self._get_client()
        if client:
            try:
                category = await asyncio.to_thread(self._classify_sync, client, text)
                if category and category in self.categories:
                    return category, {"source": "deepseek", "model": DEEPSEEK_MODEL}
                # API 返回了无法识别的类别
                logger.warning(f"DeepSeek 返回未知类别: {category}")
            except Exception as e:
                logger.error(f"DeepSeek API 分类失败: {e}")
                if not self.fallback_enabled:
                    return "其他", {"source": "deepseek", "error": str(e)}

        # 2. Fallback 到朴素贝叶斯
        if self.fallback_enabled:
            return self._classify_with_fallback(text, tokenizer)

        # 3. 无 fallback 且 API 不可用
        if not client:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置且 fallback 已禁用，无法进行邮件分类")
        return "其他", {"source": "deepseek", "model": DEEPSEEK_MODEL}

    def _classify_with_fallback(self, text: str, tokenizer=None) -> Tuple[str, Dict]:
        """使用朴素贝叶斯 fallback 分类"""
        self._ensure_fallback_trained(tokenizer)
        category, scores = self._fallback.classify(text, tokenizer)
        return category, {"source": "naive_bayes", "scores": scores}

    def _classify_sync(self, client, text: str) -> Optional[str]:
        """同步调用 DeepSeek API 进行分类"""
        prompt = CLASSIFICATION_PROMPT.format(text=text[:500])

        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,
            temperature=0.1
        )

        result = response.choices[0].message.content.strip()
        for category in self.categories:
            if category in result:
                return category
        return result if result in self.categories else None

    async def feedback(self, text: str, correct_category: str, tokenizer=None):
        """用户修正反馈 - 更新 fallback 分类器"""
        if self.fallback_enabled:
            self._ensure_fallback_trained(tokenizer)
            self._fallback.feedback(text, correct_category, tokenizer)
        logger.info(f"收到反馈: '{text[:50]}...' -> {correct_category}")


# =====================
# 朴素贝叶斯 Fallback 分类器（保留原有实现）
# =====================

# 内置种子训练数据
SEED_DATA = [
    # 工作
    ("项目进度汇报 本周完成了模块开发和测试", "工作"),
    ("会议通知 明天上午部门例会", "工作"),
    ("代码审查 请审阅PR合并请求", "工作"),
    ("任务分配 请负责用户模块开发", "工作"),
    ("周报 本周工作总结和下周计划", "工作"),
    ("需求评审 产品需求文档已更新", "工作"),
    ("bug修复 已修复登录页面问题", "工作"),
    ("部署上线 今晚进行版本发布", "工作"),

    # 通知
    ("系统升级通知 今晚进行服务器维护", "通知"),
    ("密码即将过期 请及时修改密码", "通知"),
    ("账单通知 您的月度账单已生成", "通知"),
    ("放假通知 五一假期安排", "通知"),
    ("公告 公司制度更新通知", "通知"),
    ("提醒 您的订阅即将到期", "通知"),
    ("安全提醒 您的账号在新设备登录", "通知"),
    ("服务变更通知 API接口升级说明", "通知"),

    # 广告
    ("限时优惠 全场五折起", "广告"),
    ("免费领取 新用户注册赠送", "广告"),
    ("双十一大促 购物狂欢节", "广告"),
    ("新品上市 限量抢购", "广告"),
    ("会员专享 积分兑换好礼", "广告"),
    ("优惠券 满减活动进行中", "广告"),
    ("促销活动 年终大清仓", "广告"),
    ("特惠推荐 精选商品推荐", "广告"),

    # 社交
    ("生日快乐 祝你生日快乐", "社交"),
    ("聚餐邀请 周末一起吃饭", "社交"),
    ("好久不见 最近过得怎么样", "社交"),
    ("旅行分享 海南之行照片", "社交"),
    ("节日祝福 新年快乐", "社交"),
    ("同学聚会 毕业十年聚会通知", "社交"),
    ("朋友推荐 认识新朋友", "社交"),
    ("活动邀请 周末爬山约吗", "社交"),

    # 其他
    ("测试邮件 这是一封测试", "其他"),
    ("无主题", "其他"),
    ("转发 FW 之前的邮件", "其他"),
    ("回复 RE 收到谢谢", "其他"),
]


class NaiveBayesClassifier:
    """朴素贝叶斯邮件分类器（作为 Fallback）"""

    def __init__(self, categories: List[str] = None):
        self.categories = categories or CATEGORIES
        self._category_count: Counter = Counter()
        self._word_count: Dict[str, Counter] = defaultdict(Counter)
        self._vocab: set = set()
        self._total_docs = 0
        self._trained = False

    def train(self, documents: List[Tuple[str, str]], tokenizer=None):
        """训练分类器"""
        for text, category in documents:
            if tokenizer:
                tokens = tokenizer(text)
            else:
                tokens = self._simple_tokenize(text)

            self._category_count[category] += 1
            self._total_docs += 1

            for token in tokens:
                self._word_count[category][token] += 1
                self._vocab.add(token)

        self._trained = True

    def train_with_seeds(self, tokenizer=None):
        """使用内置种子数据训练"""
        self.train(SEED_DATA, tokenizer)

    def classify(self, text: str, tokenizer=None) -> Tuple[str, Dict[str, float]]:
        """对文本进行分类"""
        if not self._trained:
            self.train_with_seeds(tokenizer)

        if tokenizer:
            tokens = tokenizer(text)
        else:
            tokens = self._simple_tokenize(text)

        scores = {}
        vocab_size = len(self._vocab)

        for category in self.categories:
            cat_count = self._category_count.get(category, 0)
            if cat_count == 0:
                scores[category] = float('-inf')
                continue

            log_prob = math.log(cat_count / self._total_docs)
            total_words_in_cat = sum(self._word_count[category].values())

            for token in tokens:
                word_freq = self._word_count[category].get(token, 0)
                log_prob += math.log((word_freq + 1) / (total_words_in_cat + vocab_size))

            scores[category] = log_prob

        best_category = max(scores, key=scores.get)
        return best_category, scores

    def feedback(self, text: str, correct_category: str, tokenizer=None):
        """用户修正反馈"""
        if tokenizer:
            tokens = tokenizer(text)
        else:
            tokens = self._simple_tokenize(text)

        self._category_count[correct_category] += 1
        self._total_docs += 1
        for token in tokens:
            self._word_count[correct_category][token] += 1
            self._vocab.add(token)

    @staticmethod
    def _simple_tokenize(text: str) -> List[str]:
        """简单分词"""
        import re
        tokens = []
        chinese_chars = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        english_words = re.findall(r'[a-zA-Z]{3,}', text)
        tokens.extend(chinese_chars)
        tokens.extend([w.lower() for w in english_words])
        return tokens
