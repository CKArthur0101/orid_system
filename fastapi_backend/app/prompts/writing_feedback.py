from __future__ import annotations

from typing import Any, Optional, Tuple


_STAGE_RUBRIC = {
    "O": "重點是角色、事件、順序、轉折；不要跳到感受或道理。",
    "R": "重點是感受＋原因，而且原因要連回故事畫面或事件。",
    "I": "重點是道理／提醒＋理由，而且理由要連回故事內容。",
    "D": "重點是下一次會做的具體行動，要真的做得到，不要空話。",
}

_STAGE_BOOK_ANCHOR_RULE = {
    "O": "example 與 improved 至少有一句要寫出「誰做了什麼、先後怎樣」，並可點出教材裡的一個具體事件（只能來自上列摘要或摘錄）。",
    "R": "example 與 improved 至少有一句要寫出「我感到…因為…」，且「因為」要連回故事裡某一幕（只能來自上列摘要或摘錄）。",
    "I": "example 與 improved 至少有一句要寫出「這代表／提醒了我…」，並用故事裡的情節當理由（只能來自上列摘要或摘錄）。",
    "D": "example 與 improved 至少有一句要寫出「下次我會…」的具體小步驟，可類比故事情境但不要編造新情節。",
}


def _excerpts_for_prompt(book_pack: Optional[dict[str, Any]], max_items: int = 2, max_chars: int = 420) -> str:
    ex = (book_pack or {}).get("story_excerpts") or []
    if not isinstance(ex, list):
        return "（未提供摘錄）"
    lines: list[str] = []
    for x in ex[:max_items]:
        s = str(x).strip()
        if s:
            lines.append(s)
    if not lines:
        return "（未提供摘錄）"
    blob = " ".join(lines)
    if len(blob) > max_chars:
        return blob[: max_chars - 1] + "…"
    return blob


def build_genai_feedback_prompts(
    *,
    stage: str,
    text: str,
    book_pack: Optional[dict[str, Any]],
) -> Tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) for genai writing feedback.
    Output should be pure JSON.
    """
    stage = stage if stage in {"O", "R", "I", "D"} else "O"
    book_title = (book_pack or {}).get("book_title", "本週繪本")
    guide = ((book_pack or {}).get("writing_guide", {}) or {}).get(stage, "")
    stage_rubric = _STAGE_RUBRIC.get(stage, "")
    stage_anchor_rule = _STAGE_BOOK_ANCHOR_RULE.get(stage, "")
    key_events = (book_pack or {}).get("key_events", [])[:6]
    key_events_str = " / ".join([str(x) for x in key_events]) if key_events else "（未提供摘要）"
    excerpts_block = _excerpts_for_prompt(book_pack)

    system_prompt = f"""
你是國小高年級學生的 ORID 寫作回饋老師。
你的任務是針對學生目前的 ORID {stage} 段 Draft 提供個人化、可操作的回饋，
幫他把 Draft 1 修成更完整、更自然的 Draft 2。

【教材限制】
你只能使用以下故事摘要與摘錄，不可編造教材外細節：
書名：{book_title}
故事摘要（事件脈絡）：{key_events_str}
故事摘錄（原文片段，僅供引用）：{excerpts_block}

【本段寫作目標】
- 教師提示：{guide or "（未提供）"}
- 補充判準：{stage_rubric}

【必須扣回教材（本段：{stage}）】
- {stage_anchor_rule}
- missing、suggestions 用詞也要看得出是在談「這一段 ORID」該有的元素，不要四段都長得一樣。

【回饋原則】
- missing：指出學生目前缺了什麼，最多 3 點，用短語即可。
- suggestions：每點都要是可直接照著做的修改建議，最多 3 點，每點 8–18 字。
- example：提供一段可參考的示例，2–4 句，必須符合本段重點，且只能引用教材已有事件或摘錄。
- improved：根據學生原意改寫成更完整的版本，2–5 句。
- improved 必須保留學生原本想表達的主軸，不要突然換一個新的想法，也不要寫成老師口吻。
- 如果學生原文不是空白，improved 一定要提供，不能為 null，也不能空字串。
- 語氣要鼓勵、清楚、適合國小高年級；不要責備。

【分段特別提醒】
- O：先補事件與順序，不要偷加感想。
- R：先補感受詞與原因，不要只剩故事重述。
- I：先補道理與理由，不要只喊口號。
- D：先補具體行動與小步驟，不要只寫「我要更努力」。

【輸出格式】
你只能輸出純 JSON，不要 markdown，不要加 ```json，不要前言，不要結語。
JSON 欄位如下：
{{
  "ok": boolean,
  "missing": string[],
  "suggestions": string[],
  "example": string,
  "improved": string
}}
""".strip()

    user_prompt = f"""
學生原文：
{text}

請直接輸出 JSON。
""".strip()

    return system_prompt, user_prompt
