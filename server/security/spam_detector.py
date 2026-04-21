"""
钓鱼/垃圾邮件检测引擎
"""
import re
import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 内置钓鱼域名黑名单
PHISHING_DOMAINS = {
    "evil.com", "malware.net", "phishing.org", "scam.com", "hack.net",
    "steal-data.com", "fake-bank.com", "login-verify.com", "secure-update.net",
    "account-alert.com", "prize-winner.com", "free-gift.net",
    "paypal-verify.com", "apple-id-check.com", "google-alert.net",
}

# Homograph 相似字符映射（常见的 Unicode 混淆字符 → ASCII 对应）
HOMOGRAPH_MAP = {
    '\u0430': 'a',  # Cyrillic а → Latin a
    '\u0435': 'e',  # Cyrillic е → Latin e
    '\u043e': 'o',  # Cyrillic о → Latin o
    '\u0440': 'p',  # Cyrillic р → Latin p
    '\u0441': 'c',  # Cyrillic с → Latin c
    '\u0443': 'y',  # Cyrillic у → Latin y
    '\u0445': 'x',  # Cyrillic х → Latin x
    '\u0456': 'i',  # Cyrillic і → Latin i
    '\u0501': 'd',  # Cyrillic ԁ → Latin d
    '\u0261': 'g',  # Latin ɡ → Latin g
    '\uff41': 'a',  # Fullwidth ａ → Latin a
    '\uff45': 'e',  # Fullwidth ｅ → Latin e
    '\uff4f': 'o',  # Fullwidth ｏ → Latin o
}

# 敏感关键词及其权重
SENSITIVE_KEYWORDS = {
    # 中文关键词
    "中奖": 3.0, "紧急转账": 4.0, "验证码": 2.0, "恭喜您": 2.5,
    "免费领取": 3.0, "限时优惠": 2.0, "点击链接": 2.5, "立即行动": 2.0,
    "银行卡": 3.0, "账号异常": 3.5, "密码过期": 3.5, "身份验证": 2.5,
    "汇款": 3.5, "中奖通知": 4.0, "退款": 2.5,
    # 英文关键词
    "you have won": 3.0, "urgent transfer": 4.0, "verify your account": 3.5,
    "congratulations": 2.5, "free gift": 3.0, "click here": 2.5,
    "act now": 2.0, "limited time": 2.0, "bank account": 3.0,
    "password expired": 3.5, "confirm identity": 3.0, "wire transfer": 3.5,
    "nigerian prince": 5.0, "lottery winner": 4.0, "claim your prize": 4.0,
}

# URL 提取正则
URL_PATTERN = re.compile(
    r'https?://[^\s<>"\')\]]+',
    re.IGNORECASE
)


@dataclass
class SpamResult:
    """垃圾邮件检测结果"""
    is_spam: bool = False
    spam_score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    flagged_urls: List[str] = field(default_factory=list)


class SpamDetector:
    """钓鱼/垃圾邮件检测器"""

    SPAM_THRESHOLD = 5.0  # 综合评分阈值

    def __init__(self):
        self.phishing_domains = PHISHING_DOMAINS
        self.sensitive_keywords = SENSITIVE_KEYWORDS

    def detect(self, subject: str, body: str, from_user: str = "") -> SpamResult:
        """
        对邮件进行垃圾/钓鱼检测

        Args:
            subject: 邮件主题
            body: 邮件正文
            from_user: 发件人

        Returns:
            SpamResult 检测结果
        """
        result = SpamResult()
        full_text = f"{subject} {body}"

        # 1. 提取并检查 URL
        urls = URL_PATTERN.findall(full_text)
        url_score = self._check_urls(urls, result)
        result.spam_score += url_score

        # 2. Homograph 攻击检测
        homo_score = self._check_homograph(full_text, result)
        result.spam_score += homo_score

        # 3. 敏感关键词评分
        keyword_score = self._check_keywords(full_text, result)
        result.spam_score += keyword_score

        # 4. 综合判定
        if result.spam_score >= self.SPAM_THRESHOLD:
            result.is_spam = True

        if result.is_spam:
            logger.warning(
                f"垃圾邮件检测: from={from_user}, score={result.spam_score:.1f}, "
                f"reasons={result.reasons}"
            )

        return result

    def _check_urls(self, urls: List[str], result: SpamResult) -> float:
        """检查 URL 黑名单"""
        score = 0.0
        for url in urls:
            # 提取域名
            domain = self._extract_domain(url)
            if domain in self.phishing_domains:
                score += 5.0
                result.flagged_urls.append(url)
                result.reasons.append(f"黑名单域名: {domain}")
        return score

    def _check_homograph(self, text: str, result: SpamResult) -> float:
        """检测 Homograph 攻击（Unicode 相似字符混淆）"""
        score = 0.0
        suspicious_chars = []
        for char in text:
            if char in HOMOGRAPH_MAP:
                suspicious_chars.append((char, HOMOGRAPH_MAP[char]))

        if suspicious_chars:
            score += 3.0 * min(len(suspicious_chars), 3)  # 最多 +9 分
            chars_desc = ", ".join(f"U+{ord(c):04X}→{a}" for c, a in suspicious_chars[:5])
            result.reasons.append(f"Homograph 可疑字符: {chars_desc}")

        return score

    def _check_keywords(self, text: str, result: SpamResult) -> float:
        """敏感关键词评分"""
        score = 0.0
        text_lower = text.lower()
        matched = []

        for keyword, weight in self.sensitive_keywords.items():
            if keyword.lower() in text_lower:
                score += weight
                matched.append(keyword)

        if matched:
            result.reasons.append(f"敏感关键词: {', '.join(matched[:5])}")

        return score

    @staticmethod
    def _extract_domain(url: str) -> str:
        """从 URL 提取域名"""
        # 去掉协议
        url = re.sub(r'^https?://', '', url)
        # 取域名部分
        domain = url.split('/')[0].split(':')[0]
        return domain.lower()
