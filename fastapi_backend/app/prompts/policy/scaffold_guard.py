from __future__ import annotations

import re


_DEFAULT_SCAFFOLDS: dict[str, str] = {
    "O": "故事中，＿＿＿做了＿＿＿。",
    "R": "我覺得＿＿＿，因為＿＿＿。",
    "I": "這個故事讓我學到＿＿＿，因為＿＿＿。",
    "D": "以後如果我遇到＿＿＿，我會＿＿＿。",
}

_BLANK_TOKENS = ("＿＿", "__", "……", "...")


def _stage_key(stage: str) -> str:
    s = (stage or "O").strip().upper()
    return s if s in _DEFAULT_SCAFFOLDS else "O"


def scaffold_for_stage(stage: str) -> str:
    return _DEFAULT_SCAFFOLDS[_stage_key(stage)]


def _looks_like_scaffold(text: str) -> bool:
    t = (text or "").strip()
    return bool(t) and any(token in t for token in _BLANK_TOKENS)


def _looks_copyable_answer(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _looks_like_scaffold(t):
        return False
    # A full answer usually contains concrete names/events plus a complete sentence.
    concrete_terms = len(re.findall(r"[\u4e00-\u9fff]{2,}", t))
    has_full_sentence = any(mark in t for mark in ("。", "！", "？"))
    has_reason_shape = "因為" in t and ("我覺得" in t or "我感到" in t or "我學到" in t)
    return len(t) > 24 and (has_full_sentence or has_reason_shape) and concrete_terms >= 1


def scaffold_feedback_example(stage: str, example: str | None) -> str | None:
    """Keep example as a scaffold, not a copyable model answer."""
    if example is None:
        return None
    text = str(example).strip()
    if not text:
        return None
    if _looks_like_scaffold(text) and len(text) <= 80:
        return text
    if _looks_copyable_answer(text) or len(text) > 80:
        return scaffold_for_stage(stage)
    return text


def scaffold_feedback_suggestions(stage: str, suggestions: list[str]) -> list[str]:
    out: list[str] = []
    for item in suggestions[:1]:
        text = str(item or "").strip()
        if not text:
            continue
        if _looks_copyable_answer(text) and "？" not in text:
            out.append(f"先想一想這一段最需要補哪一句，再用句型試寫：{scaffold_for_stage(stage)}")
        else:
            out.append(text)
    return out
