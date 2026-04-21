"""
邮件搜索引擎 - 倒排索引 + 模糊匹配
"""
import re
import logging
from typing import List, Dict, Tuple, Set
from collections import defaultdict

from server.storage.database import Database

logger = logging.getLogger(__name__)


def edit_distance(s1: str, s2: str) -> int:
    """计算两个字符串的编辑距离（Levenshtein Distance）"""
    m, n = len(s1), len(s2)
    # 优化: 如果长度差已超过阈值，直接返回大值
    if abs(m - n) > 2:
        return abs(m - n)
    
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if s1[i-1] == s2[j-1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j-1])
            prev = temp
    return dp[n]


def generate_ngrams(text: str, n: int = 3) -> Set[str]:
    """生成 N-Gram 集合"""
    text = text.lower()
    if len(text) < n:
        return {text}
    return {text[i:i+n] for i in range(len(text) - n + 1)}


class SearchEngine:
    """邮件搜索引擎 - 倒排索引 + N-Gram + 模糊匹配"""

    def __init__(self, db: Database, max_distance: int = 2, ngram_size: int = 3):
        self.db = db
        self.max_distance = max_distance
        self.ngram_size = ngram_size
        # 内存中的倒排索引
        self._index: Dict[str, Dict[str, float]] = defaultdict(dict)  # word -> {email_id: score}
        # N-Gram 索引: ngram -> {原始词}
        self._ngram_index: Dict[str, Set[str]] = defaultdict(set)
        # 已索引的词集合
        self._vocabulary: Set[str] = set()

    async def index_email(self, email_id: str, subject: str, body: str, 
                          from_user: str, to_users: str):
        """
        为一封邮件建立索引
        
        Args:
            email_id: 邮件ID
            subject: 主题
            body: 正文
            from_user: 发件人
            to_users: 收件人（逗号分隔或 JSON）
        """
        # 提取各字段的词
        fields = {
            "subject": (subject, 3.0),    # 主题权重更高
            "body": (body, 1.0),
            "from": (from_user, 2.0),
            "to": (to_users, 2.0),
        }

        for field_name, (content, weight) in fields.items():
            tokens = self._tokenize(content)
            for token in tokens:
                # 更新倒排索引
                if email_id in self._index[token]:
                    self._index[token][email_id] += weight
                else:
                    self._index[token][email_id] = weight
                
                # 更新 N-Gram 索引
                if token not in self._vocabulary:
                    self._vocabulary.add(token)
                    for ngram in generate_ngrams(token, self.ngram_size):
                        self._ngram_index[ngram].add(token)

                # 同时写入数据库持久化
                await self.db.execute(
                    "INSERT INTO search_index (keyword, email_id, field, score) VALUES (?, ?, ?, ?)",
                    (token, email_id, field_name, weight)
                )

        await self.db.commit()

    async def search(self, query: str, user_email: str, limit: int = 20) -> List[Dict]:
        """
        搜索邮件
        
        Args:
            query: 搜索关键词
            user_email: 当前用户邮箱（权限过滤）
            limit: 最大返回数量
            
        Returns:
            [{email_id, score, match_type}, ...] 按相关性排序
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 收集匹配的邮件及其分数
        results: Dict[str, float] = defaultdict(float)
        match_info: Dict[str, str] = {}  # email_id -> match_type

        for token in query_tokens:
            # 1. 精确匹配
            if token in self._index:
                for email_id, score in self._index[token].items():
                    results[email_id] += score * 2.0  # 精确匹配加权
                    match_info[email_id] = "exact"

            # 2. 模糊匹配（通过 N-Gram 候选 + 编辑距离）
            candidates = self._find_fuzzy_candidates(token)
            for candidate in candidates:
                if candidate == token:
                    continue
                dist = edit_distance(token, candidate)
                if dist <= self.max_distance:
                    fuzzy_weight = 1.0 / (dist + 1)  # 距离越小权重越高
                    if candidate in self._index:
                        for email_id, score in self._index[candidate].items():
                            results[email_id] += score * fuzzy_weight
                            if email_id not in match_info:
                                match_info[email_id] = "fuzzy"

        # 3. 数据库精确查询补充（内存索引可能未加载全部）
        for token in query_tokens:
            rows = await self.db.fetchall(
                "SELECT email_id, SUM(score) as total_score FROM search_index WHERE keyword = ? GROUP BY email_id",
                (token,)
            )
            if rows:
                for row in rows:
                    eid = row["email_id"]
                    if eid not in results:
                        results[eid] += row["total_score"]
                        match_info[eid] = "db_exact"

        # 权限过滤：只返回用户有权访问的邮件
        filtered_results = []
        for email_id, score in results.items():
            email = await self.db.fetchone(
                "SELECT from_user, to_users FROM emails WHERE email_id = ?", (email_id,)
            )
            if email:
                if user_email in (email["from_user"] or "") or user_email in (email["to_users"] or ""):
                    filtered_results.append({
                        "email_id": email_id,
                        "score": round(score, 2),
                        "match_type": match_info.get(email_id, "unknown")
                    })

        # 按分数排序
        filtered_results.sort(key=lambda x: x["score"], reverse=True)
        return filtered_results[:limit]

    def _find_fuzzy_candidates(self, token: str) -> Set[str]:
        """通过 N-Gram 索引查找模糊匹配候选词"""
        ngrams = generate_ngrams(token, self.ngram_size)
        candidates = set()
        for ngram in ngrams:
            if ngram in self._ngram_index:
                candidates.update(self._ngram_index[ngram])
        return candidates

    async def load_index_from_db(self):
        """从数据库加载索引到内存"""
        rows = await self.db.fetchall(
            "SELECT keyword, email_id, score FROM search_index"
        )
        if rows:
            for row in rows:
                keyword = row["keyword"]
                email_id = row["email_id"]
                score = row["score"]
                self._index[keyword][email_id] = self._index[keyword].get(email_id, 0) + score
                if keyword not in self._vocabulary:
                    self._vocabulary.add(keyword)
                    for ngram in generate_ngrams(keyword, self.ngram_size):
                        self._ngram_index[ngram].add(keyword)
        logger.info(f"搜索索引加载完成: {len(self._vocabulary)} 个词, {len(self._index)} 个索引项")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """简单分词"""
        if not text:
            return []
        text = text.lower()
        # 提取中文词（2字以上连续中文）和英文词（3字以上）
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        english_words = re.findall(r'[a-zA-Z]{3,}', text)
        # 处理邮箱地址
        emails = re.findall(r'[\w.]+@[\w.]+', text)
        
        tokens = chinese_words + english_words + emails
        return tokens
