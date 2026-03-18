import os
from typing import Tuple
from openai import AsyncOpenAI

# ==========================================
# Layer 1: 本地動態黑名單過濾引擎 (O(1) 攔截)
# ==========================================
# 這組詞庫未來可以從資料庫讀取，確保不動到程式碼就能更新。
LOCAL_BAD_WORDS = {
    "幹", "靠北", "靠夭", "機掰", "智障", "白痴", "白癡", "去死", "垃圾", "低能",
    "草泥馬", "操", "王八蛋"
}

# ==========================================
# Layer 2: Cloud Semantic Moderation (OpenAI)
# ==========================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

async def check_safety(text: str) -> Tuple[bool, str]:
    """
    雙層把關學生的輸入：
    回傳 (is_unsafe, unsafe_reason)
    如果 is_unsafe 為 True，代表查覺到惡意或不雅言論。
    """
    if not text or not text.strip():
        return False, ""
    
    content = text.strip()

    # 1. 先過本地防線：精準比對，直接封殺高頻髒話
    for word in LOCAL_BAD_WORDS:
        if word in content:
            return True, "請注意用字遣詞"

    # 2. 如果本地防線沒擋下，過雲端 OpenAI Moderation API：
    #    攔截隱晦的仇恨言論、霸凌、自殘等語意意圖
    if client is not None:
        try:
            resp = await client.moderations.create(input=content)
            result = resp.results[0]
            if result.flagged:
                # 抓出最嚴重的違規類別作為退回理由
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
        except Exception as e:
            # 如果 Moderation API 暫時掛掉（Timeout 或 Rate limit）
            # 在教育現場，我們通常選擇 Fail-open（相信人性本善）讓對話能繼續
            print(f"[Safety Warning] OpenAI Moderation API failed: {e}")
            pass

    # 兩道防線都安全通過
    return False, ""
