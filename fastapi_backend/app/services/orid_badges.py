"""ORID badge rules and event persistence service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OridBadgeEvent
from app.services.orid_rubric_scoring import (
    calculate_orid_sel_score,
    collect_levels_from_writing_obj,
    parse_level,
)
from app.services.orid_writing_store import ensure_orid_writing_obj

# ---------------------------------------------------------------------------
# Badge configuration
# IDs kept as badge_30/60/90 for DB / frontend asset compatibility.
# Unlock rules are stage-progress based (not total score).
# ---------------------------------------------------------------------------

BADGE_CONFIG: dict[str, dict] = {
    "badge_start": {
        "id": "badge_start",
        "name": "下筆徽章",
        "description": "先在格子裡寫一些內容，並按一次「取得回饋」或看一次寫作提示，就可以獲得。",
        "earned_description": "已獲得：你已經開始寫，也用過引導了！",
        "modal_title": "恭喜獲得下筆徽章！",
        "modal_text": "你已經開始寫下自己的想法，也使用了寫作引導。接下來把故事裡「誰做了什麼」寫清楚吧！",
    },
    "badge_30": {
        "id": "badge_30",
        "name": "松果銅徽章",
        "description": (
            "在「觀察」格把故事裡誰、做了什麼寫清楚（不要只寫感想）。"
            "等到這格出現「✓ 已完成」或完成卡，就可以獲得。"
        ),
        "earned_description": "已獲得：你已經把故事裡的人物和事件說清楚了！",
        "modal_title": "恭喜獲得松果銅徽章！",
        "modal_text": "你已經把故事裡的人物和事件說清楚了。接下來可以寫寫看：你有什麼感受？為什麼？",
    },
    "badge_60": {
        "id": "badge_60",
        "name": "松果銀徽章",
        "description": (
            "「觀察」「感受」「體會」三格都要寫到位：事件清楚、有感受與原因、有從故事學到的道理。"
            "三格都出現「✓ 已完成」就可以獲得。"
        ),
        "earned_description": "已獲得：你已經寫出事件、感受與體會了！",
        "modal_title": "恭喜獲得松果銀徽章！",
        "modal_text": "你已經寫出事件、感受，也說出從故事學到的道理。接下來可以寫一個生活裡做得到的小行動。",
    },
    "badge_90": {
        "id": "badge_90",
        "name": "松果金徽章",
        "description": (
            "四格都完成：觀察（誰做了什麼）、感受（心情與原因）、體會（學到什麼）、行動（下次要怎麼做）。"
            "都出現「✓ 已完成」就可以獲得。"
        ),
        "earned_description": "已獲得：你已經走完一整趟反思寫作！",
        "modal_title": "恭喜獲得松果金徽章！",
        "modal_text": "太棒了！你已經把觀察、感受、體會和行動都寫完了。",
    },
}

BADGE_ORDER = ["badge_start", "badge_30", "badge_60", "badge_90"]

_STAGE_KEYS = ("O", "R", "I", "D")


# ---------------------------------------------------------------------------
# Pure badge logic (no DB)
# ---------------------------------------------------------------------------


def normalize_stage_set(stages: Optional[Iterable[str]]) -> set[str]:
    out: set[str] = set()
    for s in stages or []:
        u = str(s or "").strip().upper()
        if u in _STAGE_KEYS:
            out.add(u)
    return out


def stages_passed_from_writing_obj(writing_obj: dict | None, *, mode: str = "ok") -> set[str]:
    """Derive completed stages from orid_writing_v1 JSON.

    mode="ok": experimental — stage counts if any draft feedback.ok is true
    mode="content": control — stage counts if d1/d2 has non-empty text
    """
    passed: set[str] = set()
    if not isinstance(writing_obj, dict):
        return passed
    stages = writing_obj.get("stages")
    if not isinstance(stages, dict):
        return passed

    for key in _STAGE_KEYS:
        stage_obj = stages.get(key)
        if not isinstance(stage_obj, dict):
            continue
        if mode == "content":
            text = f"{stage_obj.get('d1') or ''}{stage_obj.get('d2') or ''}".strip()
            if text:
                passed.add(key)
            continue
        feedback = stage_obj.get("feedback")
        if not isinstance(feedback, dict):
            continue
        for fb in feedback.values():
            if isinstance(fb, dict) and bool(fb.get("ok")):
                passed.add(key)
                break
    return passed


def stages_passed_from_orid_levels(orid_levels: dict[str, object] | None) -> set[str]:
    """Stages whose primary ORID criterion is level ≥ 3."""
    mapping = {"O1": "O", "R1": "R", "I1": "I", "D1": "D"}
    passed: set[str] = set()
    for cid, stage in mapping.items():
        lv = parse_level((orid_levels or {}).get(cid))
        if lv is not None and lv >= 3:
            passed.add(stage)
    return passed


def calculate_earned_badges(
    *,
    has_writing_content: bool,
    has_used_feedback_or_prompt: bool,
    stages_passed: Optional[Iterable[str]] = None,
    total_score: Optional[int] = None,  # retained for API compat; ignored for unlock
) -> list[str]:
    """Return badge IDs earned from start action + ORID stage progress.

    Badge IDs remain badge_30/60/90 for storage/UI assets, but unlock by:
      badge_30 (銅): O passed
      badge_60 (銀): O+R+I passed
      badge_90 (金): O+R+I+D passed
    """
    del total_score  # score no longer drives badges
    earned: list[str] = []

    if has_writing_content and has_used_feedback_or_prompt:
        earned.append("badge_start")

    passed = normalize_stage_set(stages_passed)
    if "O" in passed:
        earned.append("badge_30")
    if {"O", "R", "I"}.issubset(passed):
        earned.append("badge_60")
    if {"O", "R", "I", "D"}.issubset(passed):
        earned.append("badge_90")

    return earned


def get_new_badges(
    previous_badges: list[str],
    current_badges: list[str],
) -> list[str]:
    """Return badges in current_badges that are NOT in previous_badges."""
    prev_set = set(previous_badges)
    return [b for b in current_badges if b not in prev_set]


def should_show_badge_modal(new_badges: list[str]) -> bool:
    """True if there are newly earned badges to show a modal for."""
    return len(new_badges) > 0


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------


def _score_from_writing_obj(obj: dict) -> tuple[dict, int | None]:
    """Extract persisted or computed score snapshot from orid_writing_v1 JSON."""
    score_snap = obj.get("score")
    if isinstance(score_snap, dict) and score_snap.get("totalScore") is not None:
        try:
            total = int(score_snap["totalScore"])
        except (TypeError, ValueError):
            total = None
        else:
            return score_snap, total

    orid_levels, sel_levels = collect_levels_from_writing_obj(obj)
    if not orid_levels and not sel_levels:
        return {}, None
    score_result = calculate_orid_sel_score(orid_levels, sel_levels)
    return score_result, score_result.get("totalScore")


async def load_session_progress(
    db: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    week: int,
    writing_content: str | None = None,
    empty_writing_factory,
) -> dict:
    """Return earned badges and latest score for a user session/week."""
    earned = await get_earned_badges_from_db(
        db, user_id=user_id, session_id=session_id, week=week
    )

    score_result: dict = {}
    total_score: int | None = None

    if writing_content:
        obj = ensure_orid_writing_obj(
            raw_content=writing_content,
            week=week,
            empty_factory=empty_writing_factory,
        )
        score_result, total_score = _score_from_writing_obj(obj)

        writing_badges = obj.get("earnedBadges")
        if isinstance(writing_badges, list):
            earned = list(set(earned + [str(b) for b in writing_badges if b]))

    if total_score is None:
        max_stmt = select(func.max(OridBadgeEvent.total_score)).where(
            OridBadgeEvent.user_id == user_id,
            OridBadgeEvent.session_id == session_id,
            OridBadgeEvent.week == week,
            OridBadgeEvent.total_score.is_not(None),
        )
        max_res = await db.execute(max_stmt)
        max_score = max_res.scalar()
        if max_score is not None:
            total_score = int(max_score)
            score_result = {"totalScore": total_score, "maxTotal": 90}

    return {
        "earnedBadges": earned,
        "totalScore": total_score,
        "score": score_result,
    }


async def get_earned_badges_from_db(
    db: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    week: int,
) -> list[str]:
    """Fetch badge IDs already recorded for this user+session+week."""
    stmt = select(OridBadgeEvent.badge_id).where(
        OridBadgeEvent.user_id == user_id,
        OridBadgeEvent.session_id == session_id,
        OridBadgeEvent.week == week,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def record_badge_events(
    db: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    reading_id: Optional[UUID],
    week: int,
    task_type: Optional[str],
    condition: Optional[str],
    new_badge_ids: list[str],
    total_score: Optional[int],
    word_count: Optional[int],
    feedback_count: int,
    prompt_view_count: int,
    used_feedback_or_prompt: bool,
) -> list[OridBadgeEvent]:
    """Insert OridBadgeEvent rows for newly earned badges.

    Silently ignores duplicates (unique constraint) so this is safe to call
    multiple times.
    """
    saved: list[OridBadgeEvent] = []
    for badge_id in new_badge_ids:
        evt = OridBadgeEvent(
            user_id=user_id,
            session_id=session_id,
            reading_id=reading_id,
            week=week,
            task_type=task_type,
            condition=condition,
            badge_id=badge_id,
            total_score=total_score,
            word_count=word_count,
            feedback_count=feedback_count,
            prompt_view_count=prompt_view_count,
            used_feedback_or_prompt=used_feedback_or_prompt,
            created_at=datetime.now(tz=timezone.utc),
        )
        db.add(evt)
        try:
            async with db.begin_nested():
                await db.flush()
            saved.append(evt)
        except IntegrityError:
            # Duplicate badge for this user/session/week — skip silently
            pass
    return saved


async def update_session_score_snapshot(
    db: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    week: int,
    total_score: Optional[int],
) -> None:
    """Keep badge-event rows in sync with the latest computed total score."""
    if total_score is None:
        return
    stmt = (
        update(OridBadgeEvent)
        .where(
            OridBadgeEvent.user_id == user_id,
            OridBadgeEvent.session_id == session_id,
            OridBadgeEvent.week == week,
        )
        .values(total_score=total_score)
    )
    await db.execute(stmt)
