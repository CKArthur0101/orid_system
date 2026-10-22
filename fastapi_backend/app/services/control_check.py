"""Fixed-rule check for the control group.

The pass bar follows the same writing rubric as the experimental group
(level 3: a real event, a feeling with a reason, an insight with a reason,
a concrete next action). The card the student sees is prewritten: one
acknowledgement, one gap, one sentence stem. It does not quote the draft
and does not ask a follow-up question.
"""
from __future__ import annotations

from dataclasses import dataclass

from typing import Any

from app.content.synthesis_rubric import SYNTHESIS_CRITERIA_ORDER
from app.content.week_plan import writable_stages
from app.prompts.policy.turn_destination import strip_orid_stage_tag, student_o_meta_stuck
from app.services.action_pass import control_action_gap_text

_BLANK_TOKENS = ("＿＿", "____", "___", "__")

_STAGE_LABEL = {"O": "觀察", "R": "感受", "I": "體會", "D": "行動"}

_PRAISE_FAIL = {
    "O": "你已經開始寫觀察了。",
    "R": "你已經開始寫感受了。",
    "I": "你已經開始寫體會了。",
    "D": "你已經開始寫行動了。",
}
_PRAISE_PASS = {
    "O": "你寫出故事裡發生的事了。",
    "R": "你寫出感受，也寫了原因。",
    "I": "你寫出學到的事，也寫了理由。",
    "D": "你寫出下一步會做的事了。",
}
_COMPLETE = {
    "O": "觀察這一段可以了。",
    "R": "感受這一段可以了。",
    "I": "體會這一段可以了。",
    "D": "行動這一段可以了。",
}
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
class ControlCheckResult:
    ok: bool
    reply: str
    """Synthesis criterion → 3 when that part passes, else 1. None for a stage check."""
    levels: dict[str, int] | None = None


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


def _revision(praise: str, gap: str, stem: str) -> str:
    return f"你已經做到：\n{praise}\n\n再想一想：\n{gap}\n\n可以這樣修改：\n{stem}"


def _complete(praise: str, done: str, next_step: str) -> str:
    return f"你已經做到：\n{praise}\n\n本階段完成：\n{done}\n\n下一步：\n{next_step}"


def stage_next_step(week: int, stage: str, passed: set[str]) -> str:
    labels = _STAGE_LABEL
    order = list(writable_stages(week))
    remaining = [item for item in order if item not in passed]
    if remaining:
        return f"可以接著寫{labels.get(remaining[0], '下一段')}。"
    return "可以按「儲存」留下這週的寫作。"


def check_control_stage(
    *,
    stage: str,
    text: str,
    week: int,
    stages_already_passed: set[str] | None = None,
    book_pack: dict[str, Any] | None = None,
) -> ControlCheckResult:
    s = (stage or "O").strip().upper()
    if s not in _STAGE_LABEL:
        s = "O"
    gap = _stage_gap(s, text, book_pack)
    if gap:
        return ControlCheckResult(
            ok=False,
            reply=_revision(_PRAISE_FAIL[s], gap, _STEM[s]),
        )
    passed = set(stages_already_passed or set())
    passed.add(s)
    return ControlCheckResult(
        ok=True,
        reply=_complete(_PRAISE_PASS[s], _COMPLETE[s], stage_next_step(week, s, passed)),
    )


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


def check_control_synthesis(*, text: str, book_pack: dict[str, Any] | None = None) -> ControlCheckResult:
    raw = strip_orid_stage_tag(text or "").strip()
    if not raw or is_unfilled_scaffold(raw):
        levels = {key: 1 for key in SYNTHESIS_CRITERIA_ORDER}
        gap = "這還是提示句。請把空格換成你自己的話。" if raw else "請先寫一些內容再檢查。"
        return ControlCheckResult(
            ok=False,
            reply=_revision("你已經開始寫這篇了。", gap, _STEM["O"]),
            levels=levels,
        )

    flags = {
        "content_integration": _story_ok(raw),
        "coherence": _coherence_ok(raw),
        "reflection_depth": _reflection_ok(raw),
        "action_application": control_action_gap_text(raw, book_pack) is None,
    }
    levels = {key: (3 if flags[key] else 1) for key in SYNTHESIS_CRITERIA_ORDER}
    gap = _synthesis_gap(raw, book_pack)
    if gap:
        praise = "你已經寫到故事裡的事了。" if flags["content_integration"] else "你已經開始寫這篇了。"
        return ControlCheckResult(ok=False, reply=_revision(praise, gap[0], gap[1]), levels=levels)
    return ControlCheckResult(
        ok=True,
        reply=_complete(
            "你有把故事、自己的感覺、體會和之後要做的事寫進這篇。",
            "這篇四個部分都寫到了。",
            "可以按「儲存」留下這篇。",
        ),
        levels=levels,
    )
