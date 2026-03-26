from typing import Dict, List

_STAGE_HINT_RULES: Dict[str, str] = {
    "O": "優先抓角色、事件、順序、轉折。不要寫感想，不要抽象化。",
    "R": "優先抓學生提過的感受詞，以及引發感受的故事畫面或原因。",
    "I": "優先抓學生提過的提醒、道理、想法，以及支持這個想法的故事理由。",
    "D": "優先抓學生提過的下一步行動、做法、小步驟，提示要具體。",
}

_STAGE_GENERIC_HINTS: Dict[str, List[str]] = {
    "O": ["先寫誰做了什麼", "補上事情怎麼改變", "用先後順序整理"],
    "R": ["先寫你的感受", "補上為什麼會這樣想", "把感受連回故事"],
    "I": ["先寫你學到什麼", "補上故事裡的理由", "想想哪個轉折最重要"],
    "D": ["先寫下次我會", "行動要具體可做", "補上第一個小步驟"],
}


def build_writing_hints_prompts(
    stage: str,
    chat_history: list[str],
) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) to generate 2-3 short writing hints
    based primarily on what the STUDENT said in the chat history.
    """
    stage = (stage or "O").strip().upper()
    if stage not in {"O", "R", "I", "D"}:
        stage = "O"

    recent_chat = "\n".join(chat_history[-10:]) if chat_history else "(無對話紀錄)"
    generic_hints = " / ".join(_STAGE_GENERIC_HINTS[stage])

    sys = f"""
你是一位幫國小高年級學生整理寫作靈感的小助理。
學生剛完成 ORID 的 {stage} 階段口語對話，現在要開始寫右側的短文。

你的任務是：
根據剛剛的對話，產出 2–3 個很短的 Hint，幫學生回想「他自己剛剛說過什麼」，讓他更容易開始寫。

【最重要規則】
1. 優先使用「學生自己說過的內容」。
2. 老師說過的話只能當背景，不要直接改寫成 Hint。
3. 不要編造聊天裡沒出現的細節。
4. 每個 Hint 只要短語或半句話，盡量 6–15 個字。
5. Hint 要像寫作提醒，不要寫成完整評語，也不要寫成問句。
6. 每一行只輸出一個 Hint，前面用「- 」開頭。
7. 不要輸出多餘說明，不要編號，不要加前言或結語。

【本階段抓重點方式】
{_STAGE_HINT_RULES[stage]}

【若對話太空泛】
若學生自己的內容太少、太空，請改用這些通用提示中的 2–3 個：
{generic_hints}
""".strip()

    user_msg = f"""
以下是剛剛的對話紀錄（已含學生與老師）：
{recent_chat}

請直接輸出 Hint 清單。
""".strip()

    return sys, user_msg
