"""
快速回复建议生成 - 基于邮件上下文生成 3 条回复建议
"""
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# 回复模板库（按邮件类别组织）
REPLY_TEMPLATES = {
    "工作": [
        "收到，我会尽快处理。",
        "好的，已了解，稍后回复详细方案。",
        "感谢通知，我这边没有问题。",
        "了解，我会在今天内完成。",
        "收到，有问题我会及时反馈。",
        "好的，我来跟进这个任务。",
    ],
    "通知": [
        "收到通知，已知悉。",
        "好的，感谢提醒。",
        "了解，我会注意的。",
        "收到，已做好相应准备。",
    ],
    "广告": [
        "谢谢，暂时不需要。",
        "感谢推荐，我考虑一下。",
        "不感兴趣，请取消订阅。",
    ],
    "社交": [
        "谢谢！非常感谢你的邀请！",
        "好的，我到时候一定来！",
        "谢谢你的祝福！你也一样！",
        "好久不见，最近挺好的，你呢？",
        "太棒了！期待下次见面！",
    ],
    "其他": [
        "收到，谢谢。",
        "好的，了解了。",
        "感谢来信，已阅。",
    ],
}

# 关键词触发的特殊回复
KEYWORD_REPLIES = {
    "会议": ["好的，我准时参加。", "收到，会议时间没问题。", "了解，请提前发会议链接。"],
    "审查": ["好的，我会尽快审阅。", "收到，今天内完成审查。", "了解，有问题我会标注。"],
    "审阅": ["好的，我会尽快审阅。", "收到，今天内完成审查。", "了解，有问题我会标注。"],
    "部署": ["收到，我会做好部署准备。", "了解，有需要我配合的请告知。", "好的，部署前我会再确认一次。"],
    "bug": ["收到，我来排查一下。", "了解，预计今天修复。", "好的，我先复现一下问题。"],
    "修复": ["收到，我来排查一下。", "了解，预计今天修复。", "好的，我先复现一下问题。"],
    "邀请": ["谢谢邀请！我很乐意参加。", "好的，我到时候来！", "感谢！请告诉我具体时间地点。"],
    "生日": ["生日快乐！祝你万事如意！", "生日快乐！今年一定更加精彩！", "祝你生日快乐，心想事成！"],
    "祝福": ["谢谢你的祝福！你也一样！", "非常感谢！也祝你一切顺利！", "谢谢！很开心收到你的祝福。"],
    "聚餐": ["好的，我一定来！", "太好了，好久没聚了！", "没问题，到时见！"],
    "紧急": ["收到，我马上处理。", "了解，立刻着手。", "好的，正在处理中。"],
    "确认": ["已确认，没问题。", "确认收到。", "好的，已确认。"],
    "感谢": ["不客气！随时可以联系我。", "很高兴能帮到你！", "不用谢，举手之劳。"],
}

# 问句识别模式
QUESTION_PATTERNS = [
    r"[？?]",
    r"吗[？?。]?$",
    r"能否",
    r"是否",
    r"可以.*吗",
    r"怎么样",
    r"什么时候",
    r"如何",
]


class QuickReplyGenerator:
    """快速回复建议生成器"""

    def generate_replies(self, email: Dict, category: str = None,
                         num_suggestions: int = 3) -> List[Dict]:
        """
        基于邮件内容生成回复建议

        Args:
            email: 邮件信息 {subject, body, from_user, to_users}
            category: 邮件分类（可选）
            num_suggestions: 建议数量

        Returns:
            [{text, auto_to, auto_subject}, ...]
        """
        subject = email.get("subject", "")
        body = email.get("body", "")
        from_user = email.get("from_user", "")
        full_text = f"{subject} {body}"

        # 自动填充回复的收件人和主题
        auto_to = from_user
        auto_subject = f"Re: {subject}" if subject and not subject.startswith("Re:") else subject

        # 1. 优先从关键词匹配生成
        keyword_suggestions = self._match_keyword_replies(full_text)

        # 2. 检测是否为问句，添加针对性回复
        if self._is_question(full_text):
            keyword_suggestions.extend([
                "好的，可以的。",
                "没问题，我来处理。",
                "需要考虑一下，稍后回复你。",
            ])

        # 3. 从分类模板补充
        cat = category or "其他"
        template_suggestions = REPLY_TEMPLATES.get(cat, REPLY_TEMPLATES["其他"])

        # 合并并去重，优先关键词匹配
        seen = set()
        all_suggestions = []
        for text in keyword_suggestions + list(template_suggestions):
            if text not in seen:
                seen.add(text)
                all_suggestions.append(text)

        # 取前 N 条
        selected = all_suggestions[:num_suggestions]

        return [
            {
                "text": text,
                "auto_to": auto_to,
                "auto_subject": auto_subject,
            }
            for text in selected
        ]

    def _match_keyword_replies(self, text: str) -> List[str]:
        """根据关键词匹配回复"""
        matched = []
        text_lower = text.lower()
        for keyword, replies in KEYWORD_REPLIES.items():
            if keyword in text_lower:
                # 每个关键词取第一条未重复的
                for reply in replies:
                    if reply not in matched:
                        matched.append(reply)
                        break
        return matched

    def _is_question(self, text: str) -> bool:
        """检测文本是否包含问句"""
        for pattern in QUESTION_PATTERNS:
            if re.search(pattern, text):
                return True
        return False
