"""
HTML 清洗 / XSS 防护
"""
import re
import logging
from typing import Set

logger = logging.getLogger(__name__)

# 允许的安全标签（小写）
SAFE_TAGS: Set[str] = {"p", "br", "b", "i", "u", "em", "strong", "a", "ul", "ol", "li", "blockquote"}

# 允许的属性（标签 -> 属性集合）
SAFE_ATTRS = {
    "a": {"href"},
}

# 危险标签（需完全移除，包括内容）
DANGEROUS_TAGS: Set[str] = {"script", "iframe", "object", "embed", "form", "applet", "base", "link", "meta"}

# 事件属性正则（on* 属性）
EVENT_ATTR_PATTERN = re.compile(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', re.IGNORECASE)
EVENT_ATTR_PATTERN_NOQUOTE = re.compile(r'\s+on\w+\s*=\s*\S+', re.IGNORECASE)

# 匹配 HTML 标签
TAG_PATTERN = re.compile(r'<(/?)(\w+)([^>]*)(/?)>', re.IGNORECASE | re.DOTALL)

# 匹配危险标签及其内容
def _dangerous_tag_pattern(tag: str) -> re.Pattern:
    return re.compile(
        rf'<{tag}[^>]*>.*?</{tag}>|<{tag}[^>]*/?>',
        re.IGNORECASE | re.DOTALL
    )

# 匹配属性
ATTR_PATTERN = re.compile(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))', re.IGNORECASE)

# javascript: 协议检测
JS_PROTOCOL = re.compile(r'^\s*javascript\s*:', re.IGNORECASE)
DATA_PROTOCOL = re.compile(r'^\s*data\s*:', re.IGNORECASE)
VBS_PROTOCOL = re.compile(r'^\s*vbscript\s*:', re.IGNORECASE)


class HTMLSanitizer:
    """HTML 清洗器 - 防止 XSS 攻击"""

    def __init__(self):
        self.safe_tags = SAFE_TAGS
        self.safe_attrs = SAFE_ATTRS
        self.dangerous_tags = DANGEROUS_TAGS

    def sanitize(self, html: str) -> str:
        """
        清洗 HTML 内容，移除危险标签和属性
        
        Args:
            html: 原始 HTML 字符串
            
        Returns:
            清洗后的安全 HTML
        """
        if not html:
            return html

        result = html

        # 1. 移除危险标签及其全部内容
        for tag in self.dangerous_tags:
            pattern = _dangerous_tag_pattern(tag)
            result = pattern.sub('', result)

        # 2. 移除所有事件属性 (onerror, onclick, onload 等)
        result = EVENT_ATTR_PATTERN.sub('', result)
        result = EVENT_ATTR_PATTERN_NOQUOTE.sub('', result)

        # 3. 处理剩余标签：保留安全标签，移除不安全标签
        result = TAG_PATTERN.sub(lambda m: self._process_tag(m), result)

        return result

    def _process_tag(self, match: re.Match) -> str:
        """处理单个 HTML 标签"""
        is_closing = match.group(1) == '/'
        tag_name = match.group(2).lower()
        attrs_str = match.group(3)
        self_closing = match.group(4) == '/'

        # 不安全标签 → 移除整个标签（保留内容）
        if tag_name not in self.safe_tags:
            return ''

        # 安全标签 → 过滤属性
        if is_closing:
            return f'</{tag_name}>'

        safe_attrs = self._filter_attrs(tag_name, attrs_str)
        attrs_part = f' {safe_attrs}' if safe_attrs else ''
        closing = ' /' if self_closing or tag_name == 'br' else ''
        return f'<{tag_name}{attrs_part}{closing}>'

    def _filter_attrs(self, tag_name: str, attrs_str: str) -> str:
        """过滤标签属性，只保留安全属性"""
        if not attrs_str or not attrs_str.strip():
            return ''

        allowed = self.safe_attrs.get(tag_name, set())
        if not allowed:
            return ''

        safe_parts = []
        for match in ATTR_PATTERN.finditer(attrs_str):
            attr_name = match.group(1).lower()
            attr_value = match.group(2) or match.group(3) or match.group(4) or ''

            if attr_name not in allowed:
                continue

            # 检查危险协议
            if attr_name == 'href':
                if JS_PROTOCOL.match(attr_value) or DATA_PROTOCOL.match(attr_value) or VBS_PROTOCOL.match(attr_value):
                    continue

            safe_parts.append(f'{attr_name}="{attr_value}"')

        return ' '.join(safe_parts)
