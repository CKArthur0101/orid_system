from __future__ import annotations

import json
from typing import Any


def ensure_orid_writing_obj(
    *,
    raw_content: str | None,
    week: int,
    empty_factory,
) -> dict[str, Any]:
    if raw_content:
        try:
            obj = json.loads(raw_content)
            if isinstance(obj, dict) and obj.get("schema") == "orid_writing_v1":
                return obj
        except Exception:
            pass
    return empty_factory(week)


def upsert_feedback_into_stage(
    *,
    obj: dict[str, Any],
    stage: str,
    draft: str,
    text: str,
    ok: bool,
    missing: list[str],
    suggestions: list[str],
    example: str | None,
    improved: str | None,
    empty_factory,
    praise: str | None = None,
    rubric_focus: str | None = None,
    rubric_level_estimate: str | None = None,
) -> dict[str, Any]:
    stages = obj.get("stages")
    if not isinstance(stages, dict):
        obj["stages"] = empty_factory(int(obj.get("week") or 1)).get("stages", {})
        stages = obj["stages"]

    stage_obj = stages.get(stage)
    if not isinstance(stage_obj, dict):
        stages[stage] = {"d1": "", "d2": ""}
        stage_obj = stages[stage]

    stage_obj.setdefault("feedback", {})
    if isinstance(stage_obj["feedback"], dict):
        feedback_entry: dict[str, Any] = {
            "ok": ok,
            "missing": missing,
            "suggestions": suggestions,
            "example": example,
            "improved": improved,
            "praise": praise,
        }
        if rubric_focus is not None:
            feedback_entry["rubric_focus"] = rubric_focus
        if rubric_level_estimate is not None:
            feedback_entry["rubric_level_estimate"] = rubric_level_estimate
        stage_obj["feedback"][draft] = feedback_entry

    if draft == "d1":
        stage_obj["d1"] = text
    elif draft == "d2":
        stage_obj["d2"] = text

    return obj


def merge_synthesis_feedback_into_writing(
    obj: dict[str, Any],
    *,
    ai_reply: str,
    student_text: str,
) -> dict[str, Any]:
    """Persist Week-2 synthesis coach reply in orid_writing_v1 JSON (top-level)."""
    obj["synthesis_feedback"] = {
        "last_reply": ai_reply,
        "student_text_excerpt": (student_text or "")[:2000],
    }
    return obj
