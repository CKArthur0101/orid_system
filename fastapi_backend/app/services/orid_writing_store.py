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
        stage_obj["feedback"][draft] = {
            "ok": ok,
            "missing": missing,
            "suggestions": suggestions,
            "example": example,
            "improved": improved,
        }

    if draft == "d1":
        stage_obj["d1"] = text
    elif draft == "d2":
        stage_obj["d2"] = text

    return obj
