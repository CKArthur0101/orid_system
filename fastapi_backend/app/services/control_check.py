"""Fixed-rule check for the control group.

The pass bar follows the same writing rubric as the experimental group
(level 3: a real event, a feeling with a reason, an insight with a reason,
a concrete next action). The student sees checklist ticks for those rules.
A pass says the paragraph is done. It does not quote the draft and does
not ask a follow-up question.
"""
from __future__ import annotations

from dataclasses import dataclass

from typing import Any

from app.content.synthesis_rubric import SYNTHESIS_CRITERIA_ORDER
from app.prompts.policy.turn_destination import strip_orid_stage_tag, student_o_meta_stuck
from app.services.action_pass import action_level3_gap, control_action_gap_text

_BLANK_TOKENS = ("＿＿", "____", "___", "__")

_STAGE_LABEL = {"O": "觀察", "R": "感受", "I": "體會", "D": "行動"}

_STEM = {
    "O": "你可以先寫：一開始……，後來……。",
    "R": "你可以先寫：我覺得……，因為……。",
    "I": "你可以先寫：這件事讓我明白……，因為……。",
    "D": "你可以先寫：下次遇到……，我會先……。",
}

_FEELING = ("我覺得", "感到", "很溫暖", "很感人", "感動", "很好", "我喜歡", "讓人")
_PLOT = (
    "把",
    "分給",
    "藏",
    "做了",
    "最後",
    "然後",
    "一開始",
    "接著",
    "後來",
    "看到",
    "聽到",
    "爺",
    "柿",
    "離開",
    "幫忙",
    "寫信",
    "家事",
)
_EMOTION = ("開心", "難過", "生氣", "害怕", "擔心", "緊張", "失望", "感動", "驚訝", "不公平", "高興", "難受")
_INSIGHT = ("學到", "明白", "代表", "提醒", "意義", "價值", "道理", "重要")
_CONNECTORS = ("因為", "所以", "後來", "接著", "然後")


@dataclass(frozen=True)
class ControlCheckItem:
    label: str
    passed: bool


@dataclass(frozen=True)
class ControlCheckResult:
    ok: bool
    reply: str
    """Synthesis criterion → 3 when that part passes, else 1. None for a stage check."""
    levels: dict[str, int] | None = None
    checks: tuple[ControlCheckItem, ...] = ()


def is_unfilled_scaffold(text: str) -> bool:
    """A pasted sentence frame still has blanks, so it is not the student's writing."""
    raw = strip_orid_stage_tag(text or "")
    return any(token in raw for token in _BLANK_TOKENS)


def _has_sentence(text: str) -> bool:
    return "。" in text or "！" in text or "？" in text


def _stage_gap(stage: str, text: str, book_pack: dict[str, Any] | None = None) -> str | None:
    """Return the one fixed gap, or None when this stage passes."""
    t = strip_orid_stage_tag(text or "").strip()
    s = (stage or "O").strip().upper()
    if not t or is_unfilled_scaffold(t):
        return "這還是提示句。請把空格換成你自己的話。"

    if s == "O":
        if student_o_meta_stuck(t):
            return "先寫故事裡是誰做了什麼。"
        feeling = any(word in t for word in _FEELING)
        plot = any(word in t for word in _PLOT)
        if feeling and not plot and len(t) < 55:
            return "這段比較像在寫感覺。先寫故事裡誰做了什麼。"
        if len(t) < 12:
            return "內容還太少。先寫故事裡誰做了什麼。"
        if not _has_sentence(t):
            return "先把一件事寫成完整的一句，用句號收尾。"
        if len(t) < 25:
            return "可以再寫清楚先發生什麼、後來怎樣。"
        return None

    if s == "R":
        if not any(word in t for word in _EMOTION):
            return "還沒寫到一個心情。"
        if "因為" not in t:
            return "感受後面還沒寫因為什麼。"
        return None

    if s == "I":
        feeling_only = (
            any(word in t for word in ("很難過", "很開心", "生氣", "害怕", "高興"))
            and "因為" not in t
            and not any(word in t for word in _INSIGHT)
            and len(t) < 40
        )
        if feeling_only:
            return "這段比較像在寫感覺。先寫你明白或學到什麼。"
        if not any(word in t for word in ("我覺得", "提醒", "學到", "明白", "道理", "價值", "重要", "意義", "應該")):
            return "還沒寫出你明白或學到什麼。"
        if "因為" not in t and "所以" not in t:
            return "這個體會再補一個理由。"
        return None

    return control_action_gap_text(t, book_pack)


_O_WHO = "我有寫故事裡誰做了什麼"
_O_SENTENCE = "我有寫成完整的一句"
_O_LATER = "我有寫先發生什麼、後來怎樣"
_R_MOOD = "我有寫一個心情"
_R_REASON = "我有寫因為什麼"
_I_LEARNED = "我有寫我明白或學到什麼"
_I_REASON = "我有寫一個理由"
_D_STEP = "我有寫我要做的那一步"
_D_WHEN = "我有寫在什麼時候或對誰做"
_D_BOOK = "我有連到這本書的事情"
_S_STORY = "我有寫故事裡發生的事"
_S_LINK = "我有把句子接成一篇"
_S_REFLECT = "我有寫感受或體會和理由"
_S_ACTION = "我有寫做得到的下一步"

# One line per stage. The experimental rubric scores the whole stage once.
SILENT_STAGE_LABEL = {
    "O": "我有寫出故事裡的人物和事情，也能看出大致發展",
    "R": "我有寫出感受，也用故事裡的事說明原因",
    "I": "我有寫出學到的道理，也用故事說明",
    "D": "我有寫出自己做得到的行動",
}
SILENT_SYNTHESIS_LABEL = {
    "content_integration": "我有把故事、感受、體會和行動寫進這篇",
    "coherence": "我有把前後句接起來",
    "reflection_depth": "我有用故事說明自己的感受或學習原因",
    "action_application": "我有寫出自己做得到、而且呼應故事的行動",
}
_I_POINT = ("我覺得", "提醒", "學到", "明白", "道理", "價值", "重要", "意義", "應該")


def silent_stage_checks(stage: str, ok: bool) -> tuple[ControlCheckItem, ...]:
    """One tick for the whole stage. Passed only when the shared rubric says so."""
    key = (stage or "O").strip().upper()
    if key not in SILENT_STAGE_LABEL:
        key = "O"
    return (ControlCheckItem(SILENT_STAGE_LABEL[key], bool(ok)),)


def silent_synthesis_checks(levels: dict[str, int] | None) -> tuple[ControlCheckItem, ...]:
    """One tick per synthesis criterion. Passed at level 3 or 4."""
    scores = levels or {}
    return tuple(
        ControlCheckItem(SILENT_SYNTHESIS_LABEL[key], int(scores.get(key) or 0) >= 3)
        for key in ("content_integration", "coherence", "reflection_depth", "action_application")
    )


def _items(*pairs: tuple[str, bool]) -> tuple[ControlCheckItem, ...]:
    return tuple(ControlCheckItem(label, passed) for label, passed in pairs)


def _all_passed(checks: tuple[ControlCheckItem, ...]) -> tuple[ControlCheckItem, ...]:
    return tuple(ControlCheckItem(item.label, True) for item in checks)


def _stage_checks(stage: str, text: str, book_pack: dict[str, Any] | None) -> tuple[ControlCheckItem, ...]:
    """Lines the fixed rules can judge. A pass still comes from _stage_gap."""
    raw = strip_orid_stage_tag(text or "").strip()
    blank = not raw or is_unfilled_scaffold(raw)
    key = (stage or "O").strip().upper()
    if key == "O":
        plot = any(word in raw for word in _PLOT)
        feeling = any(word in raw for word in _FEELING)
        who = (
            not blank
            and not student_o_meta_stuck(raw)
            and plot
            and not (feeling and not plot and len(raw) < 55)
        )
        sentence = not blank and _has_sentence(raw) and len(raw) >= 12
        later = not blank and len(raw) >= 25
        return _items((_O_WHO, who), (_O_SENTENCE, sentence), (_O_LATER, later))
    if key == "R":
        return _items(
            (_R_MOOD, not blank and any(word in raw for word in _EMOTION)),
            (_R_REASON, not blank and "因為" in raw),
        )
    if key == "I":
        feeling_only = (
            any(word in raw for word in ("很難過", "很開心", "生氣", "害怕", "高興"))
            and "因為" not in raw
            and not any(word in raw for word in _INSIGHT)
            and len(raw) < 40
        )
        learned = not blank and not feeling_only and any(word in raw for word in _I_POINT)
        return _items(
            (_I_LEARNED, learned),
            (_I_REASON, not blank and ("因為" in raw or "所以" in raw)),
        )
    gap = "no_action" if blank else action_level3_gap(raw, book_pack)
    return _items(
        (_D_STEP, gap not in {"no_action", "vague"}),
        (_D_WHEN, gap not in {"no_action", "vague", "situation"}),
        (_D_BOOK, gap is None),
    )


def check_control_stage(
    *,
    stage: str,
    text: str,
    week: int,
    stages_already_passed: set[str] | None = None,
    book_pack: dict[str, Any] | None = None,
) -> ControlCheckResult:
    del week, stages_already_passed
    s = (stage or "O").strip().upper()
    if s not in _STAGE_LABEL:
        s = "O"
    checks = _stage_checks(s, text, book_pack)
    ok = _stage_gap(s, text, book_pack) is None
    if ok:
        checks = _all_passed(checks)
    reply = "這段可以了。" if ok else ""
    return ControlCheckResult(ok=ok, reply=reply, checks=checks)


def _story_ok(text: str) -> bool:
    return _has_sentence(text) and any(word in text for word in _PLOT) and len(text) >= 12


def _coherence_ok(text: str) -> bool:
    connectors = sum(1 for word in _CONNECTORS if word in text)
    endings = text.count("。") + text.count("！")
    return connectors >= 1 and (endings >= 2 or connectors >= 2)


def _reflection_ok(text: str) -> bool:
    has_point = any(word in text for word in _EMOTION) or any(word in text for word in _INSIGHT)
    has_reason = "因為" in text or "所以" in text
    return has_point and has_reason


def _synthesis_gap(text: str, book_pack: dict[str, Any] | None = None) -> tuple[str, str] | None:
    """First failing dimension, as (gap, stem). None when all four pass."""
    if not _story_ok(text):
        return ("還沒寫出故事裡發生的事。", _STEM["O"])
    if not _coherence_ok(text):
        return ("這幾句還沒接成一篇。可以用「因為」或「後來」再接一句。", "你可以先寫：後來……，因為……。")
    if not _reflection_ok(text):
        if not ("因為" in text or "所以" in text):
            return ("感受或體會後面再補因為什麼。", _STEM["R"])
        return ("還沒寫出你的感受，或你明白了什麼。", _STEM["I"])
    action_gap = control_action_gap_text(text, book_pack)
    if action_gap:
        return (action_gap, _STEM["D"])
    return None


def _synthesis_checks(text: str, book_pack: dict[str, Any] | None) -> tuple[ControlCheckItem, ...]:
    raw = strip_orid_stage_tag(text or "").strip()
    if not raw or is_unfilled_scaffold(raw):
        return _items((_S_STORY, False), (_S_LINK, False), (_S_REFLECT, False), (_S_ACTION, False))
    return _items(
        (_S_STORY, _story_ok(raw)),
        (_S_LINK, _coherence_ok(raw)),
        (_S_REFLECT, _reflection_ok(raw)),
        (_S_ACTION, control_action_gap_text(raw, book_pack) is None),
    )


def check_control_synthesis(*, text: str, book_pack: dict[str, Any] | None = None) -> ControlCheckResult:
    raw = strip_orid_stage_tag(text or "").strip()
    checks = _synthesis_checks(raw, book_pack)
    if not raw or is_unfilled_scaffold(raw):
        levels = {key: 1 for key in SYNTHESIS_CRITERIA_ORDER}
        return ControlCheckResult(ok=False, reply="", levels=levels, checks=checks)

    flags = {
        "content_integration": _story_ok(raw),
        "coherence": _coherence_ok(raw),
        "reflection_depth": _reflection_ok(raw),
        "action_application": control_action_gap_text(raw, book_pack) is None,
    }
    levels = {key: (3 if flags[key] else 1) for key in SYNTHESIS_CRITERIA_ORDER}
    ok = _synthesis_gap(raw, book_pack) is None
    if ok:
        checks = _all_passed(checks)
    reply = "這篇可以了。" if ok else ""
    return ControlCheckResult(ok=ok, reply=reply, levels=levels, checks=checks)
