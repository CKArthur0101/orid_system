"""Shared level-3 action gate for both conditions.

The three checks come from the existing D1 level-3 line: a situation or
person, one doable step, and the book's already-written action scope.
They do not require a particular sentence pattern.
"""
from __future__ import annotations

from typing import Any

_VAGUE = (
    "多一點",
    "多一些",
    "更努力",
    "要努力",
    "更主動",
    "主動一點",
    "幫助別人",
    "幫別人",
    "變更好",
    "更好的人",
    "變成更好",
    "要善良",
    "更用心",
    "用心一點",
)
_CONCRETE = (
    "問",
    "借",
    "說",
    "拿",
    "寫",
    "整理",
    "收",
    "洗",
    "擦",
    "講",
    "告訴",
    "聽",
    "讀",
    "鋪",
    "燙",
    "煮",
    "掃",
    "倒",
    "端",
    "切",
    "撿",
    "摺",
    "掛",
    "種",
    "撒",
    "晾",
    "分給",
    "分享",
)
_DO_WITH = ("家事", "碗", "床", "衣服", "飯", "桌子", "房間", "地板", "盤子")
_SITUATION = (
    "下次",
    "以後",
    "的時候",
    "時候",
    "時",
    "早上",
    "晚上",
    "中午",
    "放學",
    "回家",
    "吃飯",
    "每天",
    "家人",
    "媽媽",
    "爸爸",
    "同學",
    "朋友",
    "弟弟",
    "妹妹",
    "老師",
    "爺爺",
    "奶奶",
    "阿公",
    "阿嬤",
    "哥哥",
    "姊姊",
    "姐姐",
)

_CONTROL_GAP = {
    "no_action": "還沒寫出你要做的那一步。",
    "vague": "這比較像心願。請寫出你要做的那一步。",
    "situation": "再寫出這個動作是在什麼時候，或是對誰做。",
    "theme": "這個行動還沒連到這本書提醒的事情。",
}


def action_scope_markers(book_pack: dict[str, Any] | None) -> tuple[str, ...]:
    raw = (book_pack or {}).get("d_action_markers") or []
    return tuple(str(item).strip() for item in raw if str(item).strip())


def _self_clause(text: str) -> str:
    idx = text.rfind("我")
    if idx < 0:
        return text
    return text[idx : idx + 48]


def action_level3_gap(text: str, book_pack: dict[str, Any] | None = None) -> str | None:
    """Return the first missing level-3 piece, or None when the action passes.

    Codes: no_action, vague, situation, theme.
    """
    raw = (text or "").strip()
    if not raw:
        return "no_action"
    clause = _self_clause(raw)
    cleaned = clause
    for word in _VAGUE:
        cleaned = cleaned.replace(word, "")
    has_self = "我" in raw
    concrete = any(word in cleaned for word in _CONCRETE) or (
        "做" in cleaned and any(word in cleaned for word in _DO_WITH)
    )
    vague = any(word in clause for word in _VAGUE)
    if not has_self or not (concrete or vague):
        return "no_action"
    if not concrete:
        return "vague"
    if not any(word in raw for word in _SITUATION):
        return "situation"
    markers = action_scope_markers(book_pack)
    if markers and not any(word in raw for word in markers):
        return "theme"
    return None


def control_action_gap_text(text: str, book_pack: dict[str, Any] | None = None) -> str | None:
    """Fixed card line. No quotation and no question."""
    gap = action_level3_gap(text, book_pack)
    if gap is None:
        return None
    return _CONTROL_GAP[gap]


def cap_synthesis_action_level(
    levels: dict[str, int] | None,
    text: str,
    book_pack: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Keep a model score from treating a vague or off-scope action as level 3."""
    out = dict(levels or {})
    if action_level3_gap(text, book_pack) is None:
        return out
    current = int(out.get("action_application") or 2)
    out["action_application"] = min(current, 2)
    return out


def experimental_action_override(
    *,
    stage: str,
    student_text: str,
    book_pack: dict[str, Any] | None,
    ok: bool,
    missing: list[str],
    suggestions: list[str],
    rubric_meta: dict[str, Any],
    keep_model_sentences: bool,
) -> tuple[bool, list[str], list[str], dict[str, Any]]:
    """If the shared gate fails, the stage cannot pass.

    A model revision is kept. A false pass is replaced with one quoted gap
    and one question, which is the experimental card, not the fixed control card.
    """
    if (stage or "").strip().upper() != "D":
        return ok, missing, suggestions, rubric_meta
    gap = action_level3_gap(student_text, book_pack)
    if gap is None:
        return ok, missing, suggestions, rubric_meta

    out = dict(rubric_meta or {})
    levels = out.get("rubric_level_estimate")
    if isinstance(levels, dict):
        levels = dict(levels)
    else:
        levels = {}
    levels["D1"] = "2 接近"
    out["rubric_level_estimate"] = levels
    out["rubric_focus"] = "D1"
    out["action_level3_guard"] = gap

    if keep_model_sentences and missing:
        return False, missing[:1], suggestions[:1], out

    quote = (student_text or "").strip().rstrip("。！？")[:18]
    if gap == "situation":
        miss = f"你寫的「{quote}」還沒有寫出在什麼時候做，或是對誰做。"
        question = "這件事你會在什麼時候做，或是對誰做？"
    elif gap == "theme":
        title = str((book_pack or {}).get("book_title") or "這本書").strip()
        theme = str((book_pack or {}).get("d_action_student_theme") or "").strip() or "這本書提醒的事情"
        miss = f"你寫的「{quote}」還沒有連到《{title}》提醒的「{theme}」。"
        question = str((book_pack or {}).get("d_action_question") or "").strip()
        question = question or f"你想做的那一件事，和「{theme}」有什麼關係？"
    else:
        miss = f"你寫的「{quote}」還沒有寫出要做的那一步。"
        question = "你會先做哪一個動作？"
    return False, [miss], [question], out
