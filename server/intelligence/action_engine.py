"""
快捷操作引擎 - 邮件内嵌快捷操作的定义、验证与执行

支持的操作类型：
- schedule: 添加日程（解析时间/事件）
- confirm/reject: 一键确认/拒绝（二次确认 + 签名验证）
- safe_link: 安全链接跳转（URL 安全检查）
- summary: 内容摘要提取（纯文本提取）
"""
import re
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from shared.crypto import compute_hmac

logger = logging.getLogger(__name__)

# 操作类型常量
ACTION_SCHEDULE = "schedule"
ACTION_CONFIRM = "confirm"
ACTION_REJECT = "reject"
ACTION_SAFE_LINK = "safe_link"
ACTION_SUMMARY = "summary"

VALID_ACTION_TYPES = {ACTION_SCHEDULE, ACTION_CONFIRM, ACTION_REJECT,
                      ACTION_SAFE_LINK, ACTION_SUMMARY}

# URL 安全检查 - 危险协议和域名
DANGEROUS_PROTOCOLS = {"javascript:", "data:", "vbscript:", "file:"}
DANGEROUS_DOMAINS = {
    "bit.ly", "tinyurl.com", "goo.gl",  # 短链可能隐藏恶意URL
    "phishing-site.com", "malware.evil",
}


class ActionEngine:
    """快捷操作引擎"""

    def __init__(self, hmac_secret: str = "action-hmac-secret"):
        self.hmac_secret = hmac_secret

    # ==================
    # 操作定义构建
    # ==================

    def build_actions(self, email_body: str, email_id: str) -> List[Dict]:
        """
        分析邮件内容，自动生成可用的快捷操作定义列表

        Args:
            email_body: 邮件正文
            email_id: 邮件ID（用于签名）

        Returns:
            [{"type": "...", "label": "...", "data": {...}, "signature": "..."}, ...]
        """
        actions = []

        # 检测日程相关内容
        schedule_info = self._detect_schedule(email_body)
        if schedule_info:
            action = {
                "type": ACTION_SCHEDULE,
                "label": f"📅 添加日程: {schedule_info['event']}",
                "data": schedule_info,
            }
            action["signature"] = self._sign_action(email_id, action)
            actions.append(action)

        # 检测确认/拒绝场景
        if self._detect_confirmation_needed(email_body):
            for action_type, label in [(ACTION_CONFIRM, "✅ 确认"), (ACTION_REJECT, "❌ 拒绝")]:
                action = {
                    "type": action_type,
                    "label": label,
                    "data": {"email_id": email_id},
                }
                action["signature"] = self._sign_action(email_id, action)
                actions.append(action)

        # 检测URL链接
        urls = self._extract_urls(email_body)
        for url in urls[:3]:  # 最多3个链接
            safe, reason = self._check_url_safety(url)
            action = {
                "type": ACTION_SAFE_LINK,
                "label": f"🔗 {'安全链接' if safe else '⚠️ 可疑链接'}: {url[:50]}",
                "data": {"url": url, "safe": safe, "reason": reason},
            }
            action["signature"] = self._sign_action(email_id, action)
            actions.append(action)

        # 始终提供摘要操作
        summary = self._extract_summary(email_body)
        if summary:
            action = {
                "type": ACTION_SUMMARY,
                "label": "📋 复制摘要",
                "data": {"summary": summary},
            }
            action["signature"] = self._sign_action(email_id, action)
            actions.append(action)

        return actions

    # ==================
    # 操作执行
    # ==================

    def execute_action(self, email_id: str, action_def: Dict,
                       confirm: bool = False) -> Tuple[bool, str, Dict]:
        """
        执行快捷操作

        Args:
            email_id: 邮件ID
            action_def: 操作定义 {type, label, data, signature}
            confirm: 是否已二次确认（confirm/reject 类操作需要）

        Returns:
            (success, message, result_data)
        """
        action_type = action_def.get("type", "")
        signature = action_def.get("signature", "")
        data = action_def.get("data", {})

        # 验证操作类型
        if action_type not in VALID_ACTION_TYPES:
            return False, f"不支持的操作类型: {action_type}", {}

        # 验证签名
        if not self._verify_action_signature(email_id, action_def, signature):
            return False, "操作签名验证失败，拒绝执行", {}

        # 根据类型分发执行
        if action_type == ACTION_SCHEDULE:
            return self._exec_schedule(data)
        elif action_type in (ACTION_CONFIRM, ACTION_REJECT):
            if not confirm:
                return False, f"请确认执行「{action_def.get('label', '')}」操作（需要二次确认）", {
                    "need_confirm": True,
                    "action_type": action_type,
                }
            return self._exec_confirm_reject(action_type, data)
        elif action_type == ACTION_SAFE_LINK:
            return self._exec_safe_link(data)
        elif action_type == ACTION_SUMMARY:
            return self._exec_summary(data)
        else:
            return False, "未实现的操作类型", {}

    # ==================
    # 各类操作的具体执行
    # ==================

    def _exec_schedule(self, data: Dict) -> Tuple[bool, str, Dict]:
        """执行日程添加"""
        event = data.get("event", "")
        time_str = data.get("time", "")
        if not event:
            return False, "日程事件不能为空", {}
        return True, f"已添加日程: {event}" + (f" ({time_str})" if time_str else ""), {
            "event": event,
            "time": time_str,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }

    def _exec_confirm_reject(self, action_type: str, data: Dict) -> Tuple[bool, str, Dict]:
        """执行确认/拒绝"""
        email_id = data.get("email_id", "")
        status = "已确认" if action_type == ACTION_CONFIRM else "已拒绝"
        return True, f"邮件 {email_id[:8]}... {status}", {
            "email_id": email_id,
            "response": action_type,
            "responded_at": datetime.now(timezone.utc).isoformat(),
        }

    def _exec_safe_link(self, data: Dict) -> Tuple[bool, str, Dict]:
        """执行安全链接跳转"""
        url = data.get("url", "")
        safe = data.get("safe", False)
        reason = data.get("reason", "")

        if not safe:
            return False, f"链接不安全，已阻止跳转: {reason}", {
                "url": url, "blocked": True, "reason": reason
            }

        return True, f"安全链接: {url}", {
            "url": url, "safe": True
        }

    def _exec_summary(self, data: Dict) -> Tuple[bool, str, Dict]:
        """执行摘要提取"""
        summary = data.get("summary", "")
        if not summary:
            return False, "摘要内容为空", {}
        return True, "摘要已提取", {"summary": summary}

    # ==================
    # 检测与工具方法
    # ==================

    def _detect_schedule(self, text: str) -> Optional[Dict]:
        """检测日程信息（时间+事件）"""
        # 匹配中文时间模式
        time_patterns = [
            r'(明天|后天|下周[一二三四五六日]|今天|今晚|周[一二三四五六日])\s*(上午|下午|晚上)?\s*(\d{1,2}[点:：]\d{0,2})?',
            r'(\d{1,2}月\d{1,2}[日号])\s*(上午|下午|晚上)?\s*(\d{1,2}[点:：]\d{0,2})?',
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*(\d{1,2}:\d{2})?',
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                time_str = match.group(0).strip()
                # 提取事件：取时间后面的文本或整行
                event_match = re.search(r'(会议|例会|面试|聚餐|培训|分享|发布|部署|评审|上线)', text)
                event = event_match.group(0) if event_match else "日程提醒"
                return {"time": time_str, "event": event}

        return None

    def _detect_confirmation_needed(self, text: str) -> bool:
        """检测是否需要确认/拒绝"""
        confirmation_keywords = [
            "请确认", "是否同意", "请审批", "需要你的确认",
            "请回复确认", "同意吗", "可以吗", "请批准",
            "邀请你", "是否参加", "请审阅",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in confirmation_keywords)

    def _extract_urls(self, text: str) -> List[str]:
        """提取文本中的URL"""
        url_pattern = r'https?://[^\s<>"\')\]，。！？、）】}]+'
        return re.findall(url_pattern, text)

    def _check_url_safety(self, url: str) -> Tuple[bool, str]:
        """检查URL安全性"""
        url_lower = url.lower()

        # 检查危险协议
        for protocol in DANGEROUS_PROTOCOLS:
            if url_lower.startswith(protocol):
                return False, f"危险协议: {protocol}"

        # 提取域名
        domain_match = re.search(r'https?://([^/:]+)', url_lower)
        if domain_match:
            domain = domain_match.group(1)
            if domain in DANGEROUS_DOMAINS:
                return False, f"可疑域名: {domain}"

        # 检查过长URL（可能是混淆）
        if len(url) > 500:
            return False, "URL过长，可能存在混淆"

        return True, "安全"

    def _extract_summary(self, text: str, max_length: int = 200) -> str:
        """提取纯文本摘要"""
        # 移除HTML标签
        clean = re.sub(r'<[^>]+>', '', text)
        # 移除多余空白
        clean = re.sub(r'\s+', ' ', clean).strip()
        # 截断
        if len(clean) > max_length:
            clean = clean[:max_length] + "..."
        return clean

    def _sign_action(self, email_id: str, action: Dict) -> str:
        """为操作生成HMAC签名"""
        payload = f"{email_id}:{action['type']}:{json.dumps(action.get('data', {}), sort_keys=True, ensure_ascii=False)}"
        return compute_hmac(self.hmac_secret, payload)

    def _verify_action_signature(self, email_id: str, action: Dict, signature: str) -> bool:
        """验证操作签名"""
        # 临时移除signature字段再计算
        action_copy = {k: v for k, v in action.items() if k != "signature"}
        expected = self._sign_action(email_id, action_copy)
        return expected == signature
