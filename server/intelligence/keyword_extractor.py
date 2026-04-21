"""
关键词提取 - jieba 中文分词 + TF-IDF
"""
import re
import math
import logging
from typing import List, Dict, Tuple
from collections import Counter

logger = logging.getLogger(__name__)

# 中文停用词表（常见高频无意义词）
CHINESE_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
    "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些", "什么",
    "怎么", "如何", "可以", "能", "但", "而", "或", "与", "及", "等", "从",
    "为", "以", "所", "被", "对", "把", "让", "向", "于", "比", "更",
    "还", "只", "又", "已", "已经", "这个", "那个", "因为", "所以",
    "如果", "虽然", "但是", "因此", "而且", "并且", "或者", "以及",
    "关于", "对于", "通过", "进行", "使用", "可能", "需要", "应该",
    "这样", "那样", "现在", "时候", "时间", "大家", "东西", "事情",
}

# 英文停用词表
ENGLISH_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "up", "about", "into", "over", "after", "beneath", "under", "above",
    "this", "that", "these", "those", "it", "its", "my", "your", "his",
    "her", "our", "their", "which", "who", "whom", "what", "where", "when",
    "how", "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so",
    "than", "too", "very", "just", "because", "as", "until", "while",
    "and", "but", "or", "if", "then", "else", "also", "still",
}

# 中文字符检测
CHINESE_CHAR_PATTERN = re.compile(r'[\u4e00-\u9fff]')
ENGLISH_WORD_PATTERN = re.compile(r'[a-zA-Z]+')


class KeywordExtractor:
    """TF-IDF 关键词提取器"""

    def __init__(self, top_n: int = 5):
        self.top_n = top_n
        # 语料库文档频率（DF），用于 IDF 计算
        self._doc_count = 0
        self._df: Counter = Counter()  # 词 -> 出现在多少个文档中
        self._jieba_loaded = False

    def _ensure_jieba(self):
        """延迟加载 jieba"""
        if not self._jieba_loaded:
            import jieba
            jieba.setLogLevel(logging.WARNING)
            self._jieba_loaded = True

    def tokenize(self, text: str) -> List[str]:
        """
        对文本进行分词（中英文混合）
        
        Returns:
            分词后的词列表（已去停用词、去短词）
        """
        self._ensure_jieba()
        import jieba

        tokens = []

        # jieba 分词处理中文
        if CHINESE_CHAR_PATTERN.search(text):
            seg_list = jieba.cut(text)
            for word in seg_list:
                word = word.strip().lower()
                if not word:
                    continue
                # 跳过纯标点/数字
                if re.match(r'^[\d\W]+$', word):
                    continue
                # 中文词：至少 2 个字符
                if CHINESE_CHAR_PATTERN.search(word):
                    if len(word) >= 2 and word not in CHINESE_STOPWORDS:
                        tokens.append(word)
                else:
                    # 英文词：至少 3 字符
                    if len(word) >= 3 and word not in ENGLISH_STOPWORDS:
                        tokens.append(word)
        else:
            # 纯英文文本，空格分词
            words = ENGLISH_WORD_PATTERN.findall(text)
            for word in words:
                word = word.lower()
                if len(word) >= 3 and word not in ENGLISH_STOPWORDS:
                    tokens.append(word)

        return tokens

    def update_corpus(self, tokens: List[str]):
        """更新语料库统计（添加一个新文档的词汇）"""
        self._doc_count += 1
        unique_tokens = set(tokens)
        for token in unique_tokens:
            self._df[token] += 1

    def extract_keywords(self, text: str) -> List[Tuple[str, float]]:
        """
        提取关键词（TF-IDF）
        
        Args:
            text: 输入文本
            
        Returns:
            [(关键词, TF-IDF分数), ...] 按分数降序，最多 top_n 个
        """
        tokens = self.tokenize(text)
        if not tokens:
            return []

        # 计算 TF（词频）
        tf_counter = Counter(tokens)
        total_tokens = len(tokens)
        
        # 计算 TF-IDF
        scores = {}
        for word, count in tf_counter.items():
            tf = count / total_tokens
            # IDF: log(N / (df + 1)) + 1  -- 平滑处理
            df = self._df.get(word, 0)
            if self._doc_count > 0:
                idf = math.log(self._doc_count / (df + 1)) + 1
            else:
                idf = 1.0
            scores[word] = tf * idf

        # 排序返回 Top-N
        sorted_keywords = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_keywords[:self.top_n]

    def extract_keywords_simple(self, text: str) -> List[str]:
        """简化版：只返回关键词列表（不含分数）"""
        keywords = self.extract_keywords(text)
        return [kw for kw, _ in keywords]
