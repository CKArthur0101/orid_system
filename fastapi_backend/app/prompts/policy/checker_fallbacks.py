from __future__ import annotations

from typing import Any, Dict, Optional
import re

from app.prompts.policy.grounding import looks_unsafe_by_structure


_GENERIC_Q_PATTERNS = [
    r"故事發生了什麼",
    r"說說故事",
    r"有什麼感覺",
    r"提醒我們什麼",
    r"你會怎麼做",
]
_DAILY_LIFE_KEYWORDS = [
    "今天", "昨天", "明天", "早餐", "午餐", "晚餐", "便當", "飲料", "咖啡", "手機", "遊戲",
    "睡覺", "起床", "上課", "下課", "回家", "逛街", "天氣", "考試", "排骨", "雞排", "奶茶",
    "ktv", "唱歌", "夜店", "酒吧", "球賽", "nba", "wnba", "演唱會", "打電動",
]


def _one_question(text: str) -> str:
    t = (text or "").strip().replace("?", "？")
    if not t:
        return "你可以再說清楚一點嗎？"
    if "？" not in t:
        return t + "？"
    first = t.split("？", 1)[0].strip()
    return first + "？"


def _extract_anchor(student_text: str) -> str:
    t = re.sub(r"[「」『』\"'，。！？：；、（）()\[\]{}\s]+", " ", (student_text or "").strip())
    parts = [p.strip() for p in t.split(" ") if p.strip()]
    for p in parts:
        if re.search(r"[一-龥]", p) and 2 <= len(p) <= 8:
            return p
    t2 = re.sub(r"\s+", "", t)
    m = re.search(r"[一-龥]{2,8}", t2)
    return m.group(0) if m else ""


def _anchor_is_daily_life(anchor: str) -> bool:
    a = (anchor or "").strip()
    if not a:
        return False
    return any(k in a for k in _DAILY_LIFE_KEYWORDS)


def _looks_generic_question(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    return any(re.search(p, s) for p in _GENERIC_Q_PATTERNS)


def _stage_safe_fallback_question(stage: str, student_text: Optional[str] = None) -> str:
    s = (stage or "O").strip().upper()
    anchor = _extract_anchor(student_text or "")
    if _anchor_is_daily_life(anchor):
        anchor = ""

    if s == "R":
        return _one_question("故事裡哪一幕最讓你有感覺")
    if s == "I":
        return _one_question("這讓你想到什麼")
    if s == "D":
        return _one_question("下次遇到類似情況，你會先做哪一個小動作")
    return _one_question("故事裡誰做了什麼")


def clamp_checker_output(
    obj: Dict[str, Any],
    *,
    stage: Optional[str] = None,
    student_text: Optional[str] = None,
) -> Dict[str, Any]:
    unsafe_language = bool(obj.get("unsafe_language", False))
    off_topic = bool(obj.get("off_topic", False))

    unsafe_reason = obj.get("unsafe_reason", "")
    reason = obj.get("reason", "")
    suggested_question = obj.get("suggested_question", "")

    if not isinstance(unsafe_reason, str):
        unsafe_reason = ""
    if not isinstance(reason, str):
        reason = ""
    if not isinstance(suggested_question, str):
        suggested_question = ""

    unsafe_reason = unsafe_reason.strip()[:80]
    reason = reason.strip()[:80]
    suggested_question = suggested_question.strip()

    stage_norm = (stage or "O").strip().upper()
    if stage_norm not in {"O", "R", "I", "D"}:
        stage_norm = "O"

    if student_text and looks_unsafe_by_structure(student_text):
        unsafe_language = True
        if not unsafe_reason:
            unsafe_reason = "語氣不友善"

    if unsafe_language:
        off_topic = False
        if not unsafe_reason:
            unsafe_reason = "語氣不友善"
        if not reason or ("描述故事" in reason):
            reason = unsafe_reason
        if not suggested_question or _looks_generic_question(suggested_question):
            suggested_question = _stage_safe_fallback_question(stage_norm, student_text)
    else:
        if off_topic:
            if not reason:
                reason = "先回到故事"
            if not suggested_question or _looks_generic_question(suggested_question):
                suggested_question = _stage_safe_fallback_question(stage_norm, None)
        else:
            if not reason:
                reason = "OK"
            if not suggested_question:
                suggested_question = _stage_safe_fallback_question(stage_norm, student_text)

    suggested_question = (
        _one_question(suggested_question)
        if suggested_question
        else _stage_safe_fallback_question(stage_norm, student_text)
    )

    return {
        "unsafe_language": bool(unsafe_language),
        "unsafe_reason": unsafe_reason,
        "off_topic": bool(off_topic),
        "reason": reason,
        "suggested_question": suggested_question,
    }


def quick_unsafe_check(student_text: str) -> bool:
    return looks_unsafe_by_structure(student_text)
