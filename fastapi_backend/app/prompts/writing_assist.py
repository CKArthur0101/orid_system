from __future__ import annotations

from typing import Any, Optional, Tuple

ASSIST_TEXT_SPLIT = "【TIPS】"


def _normalize_stage(stage: str) -> str:
    return stage if stage in {"O", "R", "I", "D"} else "O"


def _book_title(book_pack: Optional[dict[str, Any]]) -> str:
    return str((book_pack or {}).get("book_title") or "本週繪本")


def _key_events_str(book_pack: Optional[dict[str, Any]], limit: int = 6) -> str:
    key_events = (book_pack or {}).get("key_events", [])[:limit]
    return " / ".join([str(x) for x in key_events]) if key_events else "（未提供摘要）"


def _stage_guide(stage: str, book_pack: Optional[dict[str, Any]]) -> str:
    guide = ((book_pack or {}).get("writing_guide", {}) or {}).get(stage, "")
    if guide:
        return str(guide)

    fallback = {
        "O": "先把故事中發生的事情寫清楚，重點放在角色、事件和順序。",
        "R": "寫出你的感受，並說明是故事中的哪個地方讓你有這種感受。",
        "I": "寫出你覺得這個故事提醒了我們什麼，並用故事內容支持你的想法。",
        "D": "寫出你下次遇到類似情況時，會怎麼做，行動要具體。",
    }
    return fallback.get(stage, "")


def build_writing_d1_prompts(
    *,
    stage: str,
    book_pack: Optional[dict[str, Any]],
    chat_recent_hint: str,
) -> Tuple[str, str]:
    """
    Draft 1:
    - Return (system_prompt, user_prompt)
    - Model should output ONLY one paragraph the student can paste directly.
    """
    stage = _normalize_stage(stage)
    book_title = _book_title(book_pack)
    guide = _stage_guide(stage, book_pack)
    key_events_str = _key_events_str(book_pack)

    system_prompt = f"""
你是國小高年級學生的 ORID 寫作小教練。
你的任務是根據教材摘要與最近對話線索，幫學生產生一段可直接使用的 ORID {stage} 段草稿 1。

【教材限制】你只能使用以下故事摘要，不可編造細節：
書名：{book_title}
故事摘要：{key_events_str}

【本段寫作重點】
{guide}

【輸出要求】
- 只輸出一段可直接貼上的草稿，不要標題，不要條列，不要解釋。
- 使用繁體中文。
- 2–4 句為主，內容清楚自然。
- 要像國小高年級學生會寫的句子，不要太艱深。
- 不要新增教材外人物、情節、對話、原因或場景。
- 要符合 ORID {stage} 這一段，不要跳到別的段落。
""".strip()

    user_prompt = f"""
最近對話線索：
{chat_recent_hint}

請直接產生一段 Draft 1。
""".strip()

    return system_prompt, user_prompt


def build_writing_d2_prompts(
    *,
    stage: str,
    book_pack: Optional[dict[str, Any]],
    chat_recent_hint: str,
    base_text: str,
) -> Tuple[str, str]:
    """
    Draft 2:
    - Return (system_prompt, user_prompt)
    - Model output format must be:
      <rewritten paragraph>
      【TIPS】
      1) ...
      2) ...
      3) ...
    """
    stage = _normalize_stage(stage)
    book_title = _book_title(book_pack)
    guide = _stage_guide(stage, book_pack)
    key_events_str = _key_events_str(book_pack)

    system_prompt = f"""
你是國小高年級學生的 ORID 寫作小教練。
你的任務是把學生原本的 Draft 1 改寫成更完整的 Draft 2，並給 1–3 點很短的修改提示。

【教材限制】你只能使用以下故事摘要，不可編造細節：
書名：{book_title}
故事摘要：{key_events_str}

【本段寫作重點】
{guide}

【改寫原則】
- 保留學生原本的意思，再把內容補得更完整、更清楚。
- 不可新增教材外人物、情節、對話、原因或場景。
- 用繁體中文。
- Draft 2 以 2–5 句為主，語氣自然，適合國小高年級。
- 必須符合 ORID {stage} 這一段，不要跳到別段。

【輸出格式】必須完全照下面格式輸出，不要多字：
<改寫後的段落>
{ASSIST_TEXT_SPLIT}
1) ...
2) ...
3) ...

注意：
- 第一部分只能是改寫後的段落。
- 第二部分是 1–3 點短提示。
- 不要輸出 markdown，不要加標題。
""".strip()

    user_prompt = f"""
學生原本的 Draft 1：
{base_text}

最近對話線索：
{chat_recent_hint}

請輸出 Draft 2 與修改提示。
""".strip()

    return system_prompt, user_prompt