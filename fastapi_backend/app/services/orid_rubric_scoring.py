"""ORID and SEL rubric-level helpers.

Rubric levels support formative feedback and stage-completion decisions. Formal
outcome scoring is performed by human raters, so this module intentionally does
not convert AI-estimated levels into numeric ORID, SEL, or combined scores.
"""
from __future__ import annotations

import json
import re
from typing import Optional

# Criterion IDs used in scoring (order matters for stable output)
ORID_CRITERION_IDS = ["O1", "R1", "I1", "D1"]
SEL_CRITERION_IDS = ["SEL_SA", "SEL_SM", "SEL_SOA", "SEL_RS", "SEL_RD"]

# Legacy IDs from older rubrics → current CASEL ids (for research replay)
_SEL_ID_ALIASES: dict[str, str] = {
    "SEL_EA": "SEL_SA",
    "SEL_PT": "SEL_SOA",
    "SEL_PT_R": "SEL_SOA",
    "SEL_PT_I": "SEL_SOA",
    "SEL_RA": "SEL_RD",
    # SEL_VR retired into I1; ignore for SEL scoring
}

# Chinese level label → int
_LABEL_TO_INT = {
    "起步": 1,
    "接近": 2,
    "達標": 3,
    "精進": 4,
}


def parse_level(value: object) -> Optional[int]:
    """Convert various level representations to int 1–4.

    Accepts:
      - int: 1, 2, 3, 4
      - str: "3", "3 達標", "達標", "level_3", "3_达标"
      - None → None (missing, not scored)
    """
    if value is None:
        return None
    if isinstance(value, int):
        if 1 <= value <= 4:
            return value
        return None
    s = str(value).strip()
    # Try plain integer string
    try:
        n = int(s)
        if 1 <= n <= 4:
            return n
    except ValueError:
        pass
    # Try "3 達標" or "level_3" patterns
    m = re.search(r"\b([1-4])\b", s)
    if m:
        return int(m.group(1))
    # Try Chinese label
    for label, n in _LABEL_TO_INT.items():
        if label in s:
            return n
    return None


STAGE_TO_ORID_CRITERION = {"O": "O1", "R": "R1", "I": "I1", "D": "D1"}


def normalize_sel_criterion_id(criterion_id: str, stage: str = "") -> Optional[str]:
    """Map rubric / legacy SEL id to a scoring key (CASEL five).

    ``stage`` is kept for API compatibility; social awareness is no longer split
    into separate R/I score slots — R and I both map to SEL_SOA (keep max later).
    """
    del stage  # unused; retained for call-site compatibility
    cid = (criterion_id or "").strip().upper()
    if cid in _SEL_ID_ALIASES:
        mapped = _SEL_ID_ALIASES[cid]
        return mapped if mapped in SEL_CRITERION_IDS else None
    if cid == "SEL_VR":
        return None
    if cid in SEL_CRITERION_IDS:
        return cid
    return None


def _merge_level_prefer_higher(
    store: dict[str, object],
    key: str,
    raw: object,
) -> None:
    """Write level into store; if key exists, keep the higher parsed level."""
    new_lv = parse_level(raw)
    if new_lv is None:
        return
    old_lv = parse_level(store.get(key))
    if old_lv is None or new_lv >= old_lv:
        store[key] = raw


def primary_orid_level_from_rubric_meta(
    rubric_meta: dict[str, object],
    stage: str,
) -> Optional[int]:
    """Resolve the ORID primary criterion level from rubric meta (string or dict)."""
    rl = rubric_meta.get("rubric_level_estimate")
    focus = str(rubric_meta.get("rubric_focus") or "").strip().upper()
    stage_u = (stage or "O").strip().upper()
    if isinstance(rl, dict):
        key = focus if focus in ORID_CRITERION_IDS else STAGE_TO_ORID_CRITERION.get(stage_u)
        if key:
            return parse_level(rl.get(key))
        for cid in ORID_CRITERION_IDS:
            lv = parse_level(rl.get(cid))
            if lv is not None:
                return lv
        return None
    if rl is not None and str(rl).strip():
        return parse_level(rl)
    return None


def apply_single_level_estimate(
    *,
    stage: str,
    rubric_focus: object,
    rubric_level_estimate: object,
    orid_levels: dict[str, object],
    sel_levels: dict[str, object],
) -> None:
    """Merge one feedback round's rubric estimate into level dicts.

    AI usually returns rubric_level_estimate as a plain string like ``"2 接近"``
    for the current stage's primary criterion — not a full dict of all dimensions.
    """
    if rubric_level_estimate is None:
        return

    stage_u = (stage or "").strip().upper()
    focus = str(rubric_focus or "").strip().upper()

    # Dict / JSON payload — merge all keys at once
    if isinstance(rubric_level_estimate, dict) or (
        isinstance(rubric_level_estimate, str) and rubric_level_estimate.strip().startswith("{")
    ):
        for cid, raw in extract_orid_levels_from_rubric_meta(rubric_level_estimate).items():
            orid_levels[cid] = raw
        meta: dict | None = None
        if isinstance(rubric_level_estimate, dict):
            meta = rubric_level_estimate
        elif isinstance(rubric_level_estimate, str):
            try:
                parsed = json.loads(rubric_level_estimate.strip())
                if isinstance(parsed, dict):
                    meta = parsed
            except Exception:
                meta = None
        for k, v in (meta or {}).items():
            sel_id = normalize_sel_criterion_id(str(k), stage_u)
            if sel_id:
                _merge_level_prefer_higher(sel_levels, sel_id, v)
        return

    level = parse_level(rubric_level_estimate)
    if level is None:
        return

    sel_id = normalize_sel_criterion_id(focus, stage_u)
    if sel_id or focus.startswith("SEL"):
        if sel_id:
            _merge_level_prefer_higher(sel_levels, sel_id, level)
        return

    orid_id = focus if focus in ORID_CRITERION_IDS else STAGE_TO_ORID_CRITERION.get(stage_u)
    if orid_id:
        orid_levels[orid_id] = level


def collect_levels_from_writing_obj(writing_obj: dict) -> tuple[dict[str, object], dict[str, object]]:
    """Gather rubric level estimates saved in orid_writing_v1 stage feedback."""
    orid_levels: dict[str, object] = {}
    sel_levels: dict[str, object] = {}
    stages = writing_obj.get("stages")
    if not isinstance(stages, dict):
        return orid_levels, sel_levels

    for stage_key, stage_obj in stages.items():
        if not isinstance(stage_obj, dict):
            continue
        feedback = stage_obj.get("feedback")
        if not isinstance(feedback, dict):
            continue
        for fb in feedback.values():
            if not isinstance(fb, dict):
                continue
            meta = fb.get("meta") if isinstance(fb.get("meta"), dict) else fb
            rl = meta.get("rubric_level_estimate")
            if rl is None or not str(rl).strip():
                continue
            apply_single_level_estimate(
                stage=str(stage_key),
                rubric_focus=meta.get("rubric_focus"),
                rubric_level_estimate=rl,
                orid_levels=orid_levels,
                sel_levels=sel_levels,
            )
    return orid_levels, sel_levels


def extract_orid_levels_from_rubric_meta(rubric_meta: object) -> dict[str, object]:
    """Convert AI feedback rubric_level_estimate to orid_levels dict.

    The AI returns rubric_level_estimate as a dict like:
      { "O": 3, "R": 2, "I": 3, "D": 2 }
    or with id keys like { "O1": "3 達標", ... }.
    Occasionally it may arrive as a JSON string — parse when possible.
    This normalizes both to { "O1": 3, "R1": 2, ... }.
    """
    meta: dict | None = None
    if isinstance(rubric_meta, dict):
        meta = rubric_meta
    elif isinstance(rubric_meta, str):
        s = rubric_meta.strip()
        if s.startswith("{"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, dict):
                    meta = parsed
            except Exception:
                meta = None

    mapping = {
        "O": "O1", "R": "R1", "I": "I1", "D": "D1",
        "O1": "O1", "R1": "R1", "I1": "I1", "D1": "D1",
    }
    result: dict[str, object] = {}
    for k, v in (meta or {}).items():
        normalized_key = mapping.get(str(k))
        if normalized_key:
            result[normalized_key] = v
    return result
