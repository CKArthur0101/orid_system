from __future__ import annotations

import re


ASSIST_TEXT_SPLIT = "【TIPS】"


def parse_writing_assist_response(raw: str) -> tuple[str, list[str]]:
    text = str(raw or "")
    if ASSIST_TEXT_SPLIT not in text:
        return text.strip(), []

    text_part, tips_part = text.split(ASSIST_TEXT_SPLIT, 1)
    draft_text = text_part.strip()
    tips_lines = [x.strip() for x in tips_part.strip().splitlines() if x.strip()]
    tips = [re.sub(r"^\s*\d+\)\s*", "", x) for x in tips_lines][:3]
    return draft_text, tips
