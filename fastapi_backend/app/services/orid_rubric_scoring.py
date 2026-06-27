"""ORID + SEL rubric scoring service.

Scoring:
  ORID: 4 criteria (O1, R1, I1, D1) × 10 pts each = 40 pts max
  SEL:  5 criteria (SEL_EA, SEL_PT/R, SEL_VR, SEL_PT/I, SEL_RA) × 10 pts each = 50 pts max
  Total: 90 pts max

Each criterion uses level 1–4:
  level 1 (起步)  → 25%  → 2.5 pts
  level 2 (接近)  → 50%  → 5.0 pts
  level 3 (達標)  → 75%  → 7.5 pts
  level 4 (精進)  → 100% → 10.0 pts
"""
from __future__ import annotations

import json
import re
from typing import Optional

# Criterion IDs used in scoring (order matters for stable output)
ORID_CRITERION_IDS = ["O1", "R1", "I1", "D1"]
SEL_CRITERION_IDS = ["SEL_EA", "SEL_PT_R", "SEL_VR", "SEL_PT_I", "SEL_RA"]

POINTS_PER_CRITERION = 10.0
ORID_MAX = len(ORID_CRITERION_IDS) * POINTS_PER_CRITERION   # 40
SEL_MAX = len(SEL_CRITERION_IDS) * POINTS_PER_CRITERION      # 50
TOTAL_MAX = 90

# Mapping from level int (1–4) to percentage of max_points
_LEVEL_PCT = {1: 0.25, 2: 0.50, 3: 0.75, 4: 1.00}

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


def score_criterion(level: Optional[int], max_points: float = POINTS_PER_CRITERION) -> float:
    """Convert level (1–4) to points for this criterion.

    Returns 0.0 if level is None (missing/not yet scored).
    """
    if level is None:
        return 0.0
    pct = _LEVEL_PCT.get(level, 0.0)
    return round(pct * max_points, 2)


def calculate_orid_sel_score(
    orid_levels: dict[str, object],
    sel_levels: dict[str, object],
) -> dict:
    """Calculate ORID, SEL subtotals and totalScore.

    Args:
        orid_levels: dict mapping criterion_id → raw level value.
                     Expected keys: O1, R1, I1, D1
        sel_levels:  dict mapping criterion_id → raw level value.
                     Expected keys: SEL_EA, SEL_PT_R, SEL_VR, SEL_PT_I, SEL_RA
                     (SEL_PT is shared but split by stage _R and _I)

    Returns:
        {
          "oridSubtotal": float,
          "selSubtotal": float,
          "totalScore": int,   # clamped 0–90
          "maxTotal": 90,
          "oridBreakdown": { criterion_id: float },
          "selBreakdown": { criterion_id: float },
          "missing": [criterion_id, ...],  # criteria with no level
        }
    """
    orid_breakdown: dict[str, float] = {}
    sel_breakdown: dict[str, float] = {}
    missing: list[str] = []

    for cid in ORID_CRITERION_IDS:
        raw = orid_levels.get(cid)
        level = parse_level(raw)
        if level is None:
            missing.append(cid)
        orid_breakdown[cid] = score_criterion(level)

    for cid in SEL_CRITERION_IDS:
        raw = sel_levels.get(cid)
        level = parse_level(raw)
        if level is None:
            missing.append(cid)
        sel_breakdown[cid] = score_criterion(level)

    orid_subtotal = round(sum(orid_breakdown.values()), 2)
    sel_subtotal = round(sum(sel_breakdown.values()), 2)
    total_raw = orid_subtotal + sel_subtotal
    total_score = clamp_total_score(total_raw)

    return {
        "oridSubtotal": orid_subtotal,
        "selSubtotal": sel_subtotal,
        "totalScore": total_score,
        "maxTotal": TOTAL_MAX,
        "oridBreakdown": orid_breakdown,
        "selBreakdown": sel_breakdown,
        "missing": missing,
    }


def clamp_total_score(score: float) -> int:
    """Clamp score to valid range 0–90 and return as int."""
    return max(0, min(TOTAL_MAX, round(score)))


STAGE_TO_ORID_CRITERION = {"O": "O1", "R": "R1", "I": "I1", "D": "D1"}


def normalize_sel_criterion_id(criterion_id: str, stage: str) -> Optional[str]:
    """Map rubric_focus / SEL id to scoring key (SEL_PT → SEL_PT_R or SEL_PT_I)."""
    cid = (criterion_id or "").strip().upper()
    if cid == "SEL_PT":
        if stage.upper() == "R":
            return "SEL_PT_R"
        if stage.upper() == "I":
            return "SEL_PT_I"
        return None
    if cid in SEL_CRITERION_IDS:
        return cid
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
                sel_levels[sel_id] = v
        return

    level = parse_level(rubric_level_estimate)
    if level is None:
        return

    sel_id = normalize_sel_criterion_id(focus, stage_u)
    if sel_id or focus.startswith("SEL"):
        if sel_id:
            sel_levels[sel_id] = level
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
