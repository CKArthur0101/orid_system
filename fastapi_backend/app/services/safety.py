from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Tuple

from openai import AsyncOpenAI


logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


class SafetyAction(str, Enum):
    ALLOW = "allow"
    COACH_REPHRASE = "coach_rephrase"
    BLOCK_AND_REWRITE = "block_and_rewrite"
    SUPPORT_AND_ESCALATE = "support_and_escalate"


@dataclass(frozen=True)
class SafetyDecision:
    level: int
    category: str
    action: SafetyAction
    reason: str
    student_message: str
    provider: str

    @property
    def should_stop_feedback(self) -> bool:
        return self.action is not SafetyAction.ALLOW


_ALLOW = SafetyDecision(
    level=0,
    category="normal",
    action=SafetyAction.ALLOW,
    reason="",
    student_message="",
    provider="local",
)

# Keep hard rules high precision. Ambiguous single characters such as 幹 and 操
# occur in ordinary school writing (樹幹、幹部、操場、體操、操作).
_PROFANITY_PHRASES = (
    "靠北",
    "靠夭",
    "靠邀",
    "機掰",
    "雞掰",
    "草泥馬",
    "王八蛋",
    "媽的",
    "他媽的",
    "幹你娘",
    "幹你老師",
    "操你媽",
)
_STANDALONE_PROFANITY = frozenset({"幹", "幹幹", "操"})
_INSULT_WORDS = ("白痴", "白癡", "智障", "低能", "廢物")
_SECOND_PERSON_ATTACK_RE = re.compile(
    r"(?:你|妳|你們|妳們)(?:是|很|超|真|也太|根本)?[^\n，。！？]{0,4}"
    r"(?:笨|蠢|爛|噁心|白痴|白癡|智障|低能|廢物|垃圾)"
)
_THREAT_PATTERNS = (
    re.compile(r"(?:我要|我會|老子要)?(?:打死|殺死|弄死|揍死|砍死)(?:你|妳|你們|妳們)"),
    re.compile(r"(?:你|妳|你們|妳們)(?:給我)?去死"),
    re.compile(r"殺了(?:你|妳|你們|妳們)"),
)
_SELF_HARM_PATTERNS = (
    re.compile(r"我(?:真的)?不想活(?:了|下去)?"),
    re.compile(r"我(?:好想|想要|想)?自殺"),
    re.compile(r"我(?:好想|想要|想)?去死"),
    re.compile(r"我想傷害自己"),
    re.compile(r"我想割腕"),
)
_SEXUAL_CONTENT_PATTERNS = (
    re.compile(r"(?:跟|和|與)[^\n，。！？]{1,12}上床(?!睡覺|休息)"),
    re.compile(r"(?:做愛|性交|發生性關係|口交|裸照)"),
    re.compile(r"(?:摸|碰)[^\n，。！？]{0,6}(?:胸部|下體)"),
)
_LATIN_PROFANITY_RE = re.compile(r"(?<![a-z])(?:fuck|shit|bitch)(?![a-z])", re.IGNORECASE)
_OBFUSCATION_SEPARATORS_RE = re.compile(r"[\s\u200b-\u200f\u2060._*~\-·•，,。！？!?：:；;]+")


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", (text or "").strip()).lower()
    return re.sub(r"[\u200b-\u200f\u2060]", "", normalized)


def _compact_for_matching(text: str) -> str:
    return _OBFUSCATION_SEPARATORS_RE.sub("", _normalize_text(text))


def safety_text_fingerprint(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _decision(*, level: int, category: str, reason: str, provider: str) -> SafetyDecision:
    if level == 1:
        return SafetyDecision(
            level=1,
            category=category,
            action=SafetyAction.COACH_REPHRASE,
            reason=reason,
            student_message=(
                "我知道你可能有很強的感受，但這個說法不適合放在作文裡。"
                "請換成不傷人的說法，例如先寫『我覺得很生氣，因為……』。"
            ),
            provider=provider,
        )
    if level == 2:
        return SafetyDecision(
            level=2,
            category=category,
            action=SafetyAction.BLOCK_AND_REWRITE,
            reason=reason,
            student_message=(
                "可以說出你的感受，但不要用傷人的話指責別人。"
                "請改寫成發生了什麼事，以及你當時有什麼感覺。"
            ),
            provider=provider,
        )
    if level == 3:
        if category in {"sexual_content", "sexual_minors"}:
            return SafetyDecision(
                level=3,
                category=category,
                action=SafetyAction.BLOCK_AND_REWRITE,
                reason=reason,
                student_message=(
                    "這段包含不適合放在寫作作業裡的性暗示或私密內容，所以現在不能送出。"
                    "請改寫成與故事和閱讀心得有關的內容；如果有人讓你感到不舒服，請告訴老師或信任的大人。"
                ),
                provider=provider,
            )
        return SafetyDecision(
            level=3,
            category=category,
            action=SafetyAction.BLOCK_AND_REWRITE,
            reason=reason,
            student_message=(
                "這段話可能會傷害或威脅別人，所以現在不能送出。"
                "請停止使用威脅或歧視的說法，並找老師協助你處理這件事。"
            ),
            provider=provider,
        )
    return SafetyDecision(
        level=4,
        category=category,
        action=SafetyAction.SUPPORT_AND_ESCALATE,
        reason=reason,
        student_message=(
            "謝謝你把這件事說出來。請先找身邊信任的老師或大人陪你，"
            "現在不要一個人處理；系統也會留下需要老師關心的提醒。"
        ),
        provider=provider,
    )


def classify_local_safety(text: str) -> SafetyDecision:
    normalized = _normalize_text(text)
    compact = _compact_for_matching(text)
    if not compact:
        return _ALLOW

    for pattern in _SELF_HARM_PATTERNS:
        if pattern.search(compact):
            return _decision(
                level=4,
                category="self_harm_intent",
                reason="涉及自傷或危機訊號",
                provider="local",
            )

    for pattern in _THREAT_PATTERNS:
        if pattern.search(compact):
            return _decision(
                level=3,
                category="threat",
                reason="包含針對他人的威脅",
                provider="local",
            )

    for pattern in _SEXUAL_CONTENT_PATTERNS:
        if pattern.search(compact):
            return _decision(
                level=3,
                category="sexual_content",
                reason="涉及性暗示或不適齡私密內容",
                provider="local",
            )

    if _SECOND_PERSON_ATTACK_RE.search(compact):
        return _decision(
            level=2,
            category="harassment",
            reason="包含針對他人的人身攻擊",
            provider="local",
        )

    if compact in _STANDALONE_PROFANITY or any(phrase in compact for phrase in _PROFANITY_PHRASES):
        return _decision(
            level=1,
            category="profanity",
            reason="包含不雅用語",
            provider="local",
        )

    if any(word in compact for word in _INSULT_WORDS) or _LATIN_PROFANITY_RE.search(normalized) or _LATIN_PROFANITY_RE.search(compact):
        return _decision(
            level=1,
            category="profanity",
            reason="包含不雅或羞辱用語",
            provider="local",
        )

    return _ALLOW


def _category_is_true(categories: dict[str, Any], *names: str) -> bool:
    normalized = {
        re.sub(r"[-/]", "_", str(key)): bool(value)
        for key, value in categories.items()
    }
    for name in names:
        if normalized.get(re.sub(r"[-/]", "_", name), False):
            return True
    return False


def _decision_from_moderation(categories: dict[str, Any], *, writing_coach: bool) -> SafetyDecision:
    if _category_is_true(categories, "self-harm", "self-harm/intent", "self-harm/instructions"):
        return _decision(
            level=4,
            category="self_harm",
            reason="涉及自傷或危機訊號",
            provider="moderation",
        )
    if _category_is_true(categories, "sexual/minors"):
        return _decision(
            level=3,
            category="sexual_minors",
            reason="涉及未成年不當性內容",
            provider="moderation",
        )
    if _category_is_true(categories, "sexual"):
        return _decision(
            level=3,
            category="sexual_content",
            reason="涉及性暗示或不適齡私密內容",
            provider="moderation",
        )
    if _category_is_true(
        categories,
        "harassment/threatening",
        "hate/threatening",
        "hate",
        "violence/graphic",
        "illicit/violent",
    ):
        return _decision(
            level=3,
            category="high_risk",
            reason="涉及威脅、仇恨或其他高風險內容",
            provider="moderation",
        )
    if _category_is_true(categories, "harassment"):
        return _decision(
            level=2,
            category="harassment",
            reason="包含針對他人的人身攻擊",
            provider="moderation",
        )
    # Plain story violence is not automatically unsafe in a children's-book
    # writing task. Graphic or threatening violence was handled above.
    if not writing_coach and _category_is_true(categories, "violence", "illicit"):
        return _decision(
            level=3,
            category="unsafe_content",
            reason="包含高風險內容",
            provider="moderation",
        )
    return _ALLOW


async def classify_safety(text: str, *, writing_coach: bool = False) -> SafetyDecision:
    if not text or not text.strip():
        return _ALLOW

    local = classify_local_safety(text)
    if local.should_stop_feedback or client is None:
        return local

    try:
        response = await client.moderations.create(
            model="omni-moderation-latest",
            input=text.strip(),
        )
        categories = response.results[0].categories.model_dump()
        return _decision_from_moderation(categories, writing_coach=writing_coach)
    except Exception:
        # Fail open for availability, while keeping deterministic local checks.
        logger.warning("OpenAI moderation failed; continuing with local safety only")
        return local


async def check_safety(text: str, *, writing_coach: bool = False) -> Tuple[bool, str]:
    """Backward-compatible wrapper for older callers."""
    decision = await classify_safety(text, writing_coach=writing_coach)
    return decision.should_stop_feedback, decision.reason
