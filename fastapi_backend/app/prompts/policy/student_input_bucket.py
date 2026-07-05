"""
Rule-based coarse bucketing of student free text for prompt tone (not NLU).

Heuristics: length, CJK vs Latin ratios, repeated characters, obvious keyboard spam,
punctuation-heavy blobs. Stable and unit-testable.
"""

from __future__ import annotations

import re
from typing import Final

# Bucket ids used in prompts and tests.
BUCKET_NORMAL: Final = "normal"
BUCKET_TOO_SHORT: Final = "too_short"
BUCKET_LIKELY_GIBBERISH: Final = "likely_gibberish"
BUCKET_LATIN_HEAVY: Final = "latin_heavy"
BUCKET_MIXED_SCRIPT: Final = "mixed_script"
BUCKET_EMPTY: Final = "empty"

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_REPEAT_RE = re.compile(r"(.)\1{4,}")  # same char 5+ in a row


def truncate_student_draft_excerpt(text: str, *, max_len: int = 400) -> str:
    """Single-line-ish excerpt for prompts; no PII logic beyond truncation."""
    t = " ".join((text or "").split())
    if not t:
        return "（無內容）"
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def classify_student_input(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return BUCKET_EMPTY

    if len(t) < 6:
        return BUCKET_TOO_SHORT

    cjk = len(_CJK_RE.findall(t))
    lat = len(_LATIN_RE.findall(t))
    letters = cjk + lat
    # 8+ 字的全中文句子（如「看到阿松爺爺吃地瓜」）視為正常草稿，不算 too_short。
    if cjk >= 8 and lat == 0 and len(t) >= 8:
        pass
    elif len(t) < 10:
        return BUCKET_TOO_SHORT
    if letters == 0:
        return BUCKET_LIKELY_GIBBERISH

    if _REPEAT_RE.search(t):
        return BUCKET_LIKELY_GIBBERISH

    tl = t.lower()
    if any(p in tl for p in ("asdf", "qwert", "hjkl", "zxcv")) and len(t) <= 48:
        return BUCKET_LIKELY_GIBBERISH

    uniq_ratio = len(set(t)) / max(len(t), 1)
    if len(t) >= 16 and uniq_ratio < 0.18 and cjk < 4:
        return BUCKET_LIKELY_GIBBERISH

    punct = sum(1 for ch in t if ch in '.,;:!?。，、；：！？…~～""''（）()[]【】「」『』—-_')
    if len(t) >= 8 and punct / len(t) > 0.55:
        return BUCKET_LIKELY_GIBBERISH

    if cjk >= 3 and lat >= 6:
        return BUCKET_MIXED_SCRIPT

    if len(t) >= 14 and letters > 0 and lat / letters > 0.72 and cjk < 4:
        return BUCKET_LATIN_HEAVY

    if cjk < 3 and len(t) < 28:
        return BUCKET_TOO_SHORT

    return BUCKET_NORMAL


_BUCKET_TONE_HINTS: dict[str, str] = {
    BUCKET_EMPTY: "輸入為空：missing 溫和請學生貼上想被看的句子；praise 鼓勵先寫一句即可。",
    BUCKET_TOO_SHORT: "輸入偏短：語氣更耐心，引導多寫一句具體內容；不要求面面俱到。",
    BUCKET_LIKELY_GIBBERISH: "輸入疑似亂打：missing 用關心口吻請學生用完整句子重說一次；避免責備。",
    BUCKET_LATIN_HEAVY: "輸入以英文為主：praise/missing/suggestions 以英文為主、仍可帶一句繁中對照若需要。",
    BUCKET_MIXED_SCRIPT: (
        "中英混雜：praise 先承接原文裡的人／事／中英詞；missing 只抓一個主點。"
        "suggestions 可帶一句「本段練習建議接下來用繁中文寫完，老師好改、同學也看得懂」（一句即可，勿說教）；"
        "仍只輸出 JSON。"
    ),
    BUCKET_NORMAL: "輸入長度正常：維持既有 JSON 規則與口吻。",
}


def bucket_tone_hint_zh(bucket: str) -> str:
    """One line for JSON-layer system prompts (Chinese, compact)."""
    return _BUCKET_TONE_HINTS.get(bucket, _BUCKET_TONE_HINTS[BUCKET_NORMAL])


def skip_book_grounding_enforcement(
    bucket: str,
    *,
    student_text: str = "",
    book_pack: object | None = None,
) -> bool:
    """
    When True, do not treat student text as a 'story draft' for book grounding.

    Keyboard spam / empty / very short inputs are often falsely flagged as 'ungrounded'.
  """
    if bucket in (BUCKET_LIKELY_GIBBERISH, BUCKET_EMPTY):
        return True
    if bucket == BUCKET_TOO_SHORT:
        from app.prompts.policy.grounding import looks_story_related_to_book, normalize_match_text

        core = normalize_match_text(student_text)
        if len(core) >= 6 and looks_story_related_to_book(student_text, book_pack):
            if any(k in core for k in ("看到", "聽到", "吃", "拿", "把", "給", "爺", "柿", "藏", "砍")):
                return False
        return True
    return False
