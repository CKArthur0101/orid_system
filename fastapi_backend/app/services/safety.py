import os
import re
import logging
from typing import Tuple
from openai import AsyncOpenAI

# ==========================================
# Layer 1: 本地快速過濾
# ==========================================
LOCAL_BAD_WORDS = {
    "幹", "靠北", "靠夭", "機掰", "智障", "白痴", "白癡", "去死", "垃圾", "低能",
    "草泥馬", "操", "王八蛋", "廢物"
}

LOCAL_ATTACK_PATTERNS = [
    r"(你|妳|他|她|你們|妳們)\s*(是|很|超|真|也太)?\s*[^ \n]{0,4}(笨|蠢|爛|噁|討厭|白痴|白癡|智障|低能|廢物)",
    r"(你|妳|他|她)\s*(去|給我去)\s*(死|滾)",
]

# ==========================================
# Layer 2: OpenAI Moderation
# ==========================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower())


def _local_reason(text: str) -> str:
    t = _normalize_text(text)
    if any(w in t for w in ("去死", "滾")):
        return "包含攻擊性語句"
    if any(w in t for w in ("白痴", "白癡", "智障", "低能", "廢物")):
        return "包含人身攻擊"
    return "請注意用字遣詞"


async def check_safety(text: str, *, writing_coach: bool = False) -> Tuple[bool, str]:
    """
    雙層把關學生輸入：
    回傳 (is_unsafe, unsafe_reason)

    writing_coach=True 時僅跑本地髒話／人身攻擊過濾，不呼叫雲端 Moderation。
    國小反思寫作常出現學生誤記情節（如把「砍樹」記成「打人」），
    應交由書本 grounding 與回饋引導，而非直接 400 擋下。
    """
    if not text or not text.strip():
        return False, ""

    content = text.strip()
    content_norm = _normalize_text(content)

    # 1. 本地快速過濾：髒話、直接辱罵、明顯攻擊
    for word in LOCAL_BAD_WORDS:
        if word in content_norm:
            return True, _local_reason(content)

    for pattern in LOCAL_ATTACK_PATTERNS:
        if re.search(pattern, content_norm):
            return True, "包含人身攻擊"

    # 2. 雲端 Moderation：補語意層（寫作回饋路徑略過，改由 grounding 溫和引導）
    if writing_coach:
        return False, ""

    if client is not None:
        try:
            resp = await client.moderations.create(input=content)
            result = resp.results[0]
            if result.flagged:
                flagged_cats = [k for k, v in result.categories.model_dump().items() if v]
                reason = "包含不當言論"
                if "harassment" in flagged_cats or "harassment_threatening" in flagged_cats:
                    reason = "涉及霸凌或騷擾"
                elif "hate" in flagged_cats or "hate_threatening" in flagged_cats:
                    reason = "涉及仇恨與歧視言論"
                elif "self-harm" in flagged_cats or "self-harm_intent" in flagged_cats:
                    reason = "涉及自殘或危險暗示"
                elif "sexual" in flagged_cats or "sexual_minors" in flagged_cats:
                    reason = "涉及不當性暗示內容"
                return True, reason
        except Exception:
            # 教學現場採 fail-open，避免 moderation 短暫失敗就整段流程中斷
            logger.warning("OpenAI moderation failed; continuing with local safety only")

    return False, ""
