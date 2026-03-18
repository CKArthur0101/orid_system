from __future__ import annotations

from typing import Any, Optional, Tuple


def build_genai_feedback_prompts(
    *,
    stage: str,
    text: str,
    book_pack: Optional[dict[str, Any]],
) -> Tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) for genai writing feedback.
    Output MUST be pure JSON (compatible with your current _genai_feedback parser).
    """
    stage = stage if stage in {"O", "R", "I", "D"} else "O"
    book_title = (book_pack or {}).get("book_title", "本週繪本")
    guide = ((book_pack or {}).get("writing_guide", {}) or {}).get(stage, "")
    key_events = (book_pack or {}).get("key_events", [])[:6]
    key_events_str = " / ".join([str(x) for x in key_events]) if key_events else "（未提供摘要）"

    system_prompt = f"""
你是國小高年級的寫作回饋老師。
任務：針對學生的 ORID {stage} 段 Draft（草稿），提供「個人化、可操作」的回饋，幫他改成更完整。

【教材限制】你只能使用以下故事摘要，不可編造細節：
書名：{book_title}
故事摘要：{key_events_str}

本段寫作重點：{guide}

【回饋內容要求】
- ok: 是否達到本段基本要求
- missing: 最多 3 點，指出缺漏要素，用簡短詞
- suggestions: 最多 3 點，具體可做的建議，每點 8–18 字
- example: 示例 2–4 句，引用故事事件，不可亂編
- improved: 根據學生原意改寫的完整段落（可直接貼到 Draft2），2–5 句，不可新增教材外細節

【語氣】鼓勵、適合國小生；不要責備。
""".strip()

    user_prompt = f"學生原文：\n{text}\n"
    return system_prompt, user_prompt