"""RASF plain-language context for feedback narration (LLM2)."""
from __future__ import annotations

from typing import Any, Optional

from app.services.orid_rubric_scoring import STAGE_TO_ORID_CRITERION, parse_level


def _level_desc(criterion: dict[str, Any], level: int) -> str:
    levels = criterion.get("levels")
    if not isinstance(levels, list):
        return ""
    for lv in levels:
        if isinstance(lv, dict):
            label = str(lv.get("label") or "")
            if parse_level(label) == level or str(level) in label:
                return str(lv.get("desc") or "").strip()
        elif isinstance(lv, str) and parse_level(lv) == level:
            return lv.strip()
    return ""


def build_rasf_narration_context(
    *,
    stage: str,
    book_pack: Optional[dict[str, Any]],
    rubric_focus: object,
    rubric_level_estimate: object,
    student_anchor_quote: object = None,
    draft_next_step: object = None,
) -> dict[str, Any]:
    """Build student-facing RASF hints for narration (no level numbers in output)."""
    stage_u = (stage or "O").strip().upper()
    focus = str(rubric_focus or "").strip().upper() or STAGE_TO_ORID_CRITERION.get(stage_u, "O1")

    current_level: Optional[int] = None
    if isinstance(rubric_level_estimate, dict):
        current_level = parse_level(rubric_level_estimate.get(focus))
    elif rubric_level_estimate is not None:
        current_level = parse_level(rubric_level_estimate)

    current_plain = ""
    next_plain = ""
    if isinstance(book_pack, dict):
        wr = book_pack.get("writing_rubric")
        if isinstance(wr, dict):
            by_stage = wr.get("by_stage")
            if isinstance(by_stage, dict):
                items = by_stage.get(stage_u) or []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    if str(it.get("id") or "").strip().upper() != focus:
                        continue
                    if current_level is not None:
                        current_plain = _level_desc(it, current_level)
                        if current_level < 3:
                            next_plain = _level_desc(it, current_level + 1)
                        elif current_level == 3:
                            next_plain = _level_desc(it, 4)
                    break

    out: dict[str, Any] = {
        "focus": focus,
        "current_level": current_level,
        "current_level_plain": current_plain or None,
        "next_level_plain": next_plain or None,
    }
    quote = str(student_anchor_quote or "").strip()
    if quote:
        out["student_anchor_quote"] = quote
    step = str(draft_next_step or "").strip()
    if step:
        out["draft_next_step"] = step
    return out
