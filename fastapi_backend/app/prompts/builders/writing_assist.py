from __future__ import annotations

from typing import Any, Optional, Tuple

from app.prompts.parsers.writing_assist import ASSIST_TEXT_SPLIT
from app.prompts.templates.writing_assist import (
    WRITING_ASSIST_FALLBACK_STAGE_GUIDE,
    WRITING_ASSIST_SYSTEM_ROLE,
)


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
    return WRITING_ASSIST_FALLBACK_STAGE_GUIDE.get(stage, "")


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
{WRITING_ASSIST_SYSTEM_ROLE}
你的任務是根據教材摘要與最近對話線索，幫學生產生一段可直接使用的 ORID {stage} 段 Draft 1。

【教材限制】
你只能使用以下故事摘要，不可編造教材外細節：
書名：{book_title}
故事摘要：{key_events_str}

【本段寫作重點】
{guide}

【Draft 1 原則】
- 優先使用最近對話中學生自己提過的內容與用詞。
- 若對話線索不多，寫得保守一點，也不要亂補細節。
- 內容要像國小高年級學生會寫的句子，不要太像老師或 AI。
- 只做本段該做的事，不要跳到別段。
- 2–4 句為主，句子自然清楚。

【輸出要求】
- 只輸出一段可直接貼上的草稿，不要標題，不要條列，不要解釋。
- 使用繁體中文。
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
{WRITING_ASSIST_SYSTEM_ROLE}
你的任務是把學生原本的 Draft 1 補強成更完整的 Draft 2，並附上 1–3 點很短的修改提示。

【教材限制】
你只能使用以下故事摘要，不可編造教材外細節：
書名：{book_title}
故事摘要：{key_events_str}

【本段寫作重點】
{guide}

【改寫原則】
- 以學生原本的意思為主，只補清楚、不亂改主軸。
- 優先補學生本來缺的地方：順序、原因、理由、具體做法。
- 不可新增教材外人物、情節、對話、原因或場景。
- Draft 2 以 2–5 句為主，語氣自然，適合國小高年級。
- 不要寫成老師評語，也不要突然變成另一篇完全不同的作文。
- Tips 要短，像修改提醒，不要重複整段內容。

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
