"""ORID badge rules and event persistence service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OridBadgeEvent
from app.services.orid_rubric_scoring import (
    calculate_orid_sel_score,
    collect_levels_from_writing_obj,
)
from app.services.orid_writing_store import ensure_orid_writing_obj

# ---------------------------------------------------------------------------
# Badge configuration
# ---------------------------------------------------------------------------

BADGE_CONFIG: dict[str, dict] = {
    "badge_start": {
        "id": "badge_start",
        "name": "下筆徽章",
        "description": "開始寫作，並使用一次回饋或提示，就可以獲得。",
        "earned_description": "你已經開始寫下自己的想法，也使用了寫作引導，繼續完成今天的反思任務吧！",
        "modal_title": "恭喜獲得下筆徽章！",
        "modal_text": "你已經開始寫下自己的想法，也使用了寫作引導，繼續完成今天的反思任務吧！",
    },
    "badge_30": {
        "id": "badge_30",
        "name": "松果銅徽章",
        "description": "總分達到 30/90，就可以獲得。",
        "earned_description": "你已經完成基本的反思內容，接下來可以試著寫得更具體。",
        "modal_title": "恭喜獲得松果銅徽章！",
        "modal_text": "你已經完成基本的反思內容，接下來可以試著寫得更具體。",
    },
    "badge_60": {
        "id": "badge_60",
        "name": "松果銀徽章",
        "description": "總分達到 60/90，就可以獲得。",
        "earned_description": "你的反思越來越完整了，可以再加強想法之間的連結。",
        "modal_title": "恭喜獲得松果銀徽章！",
        "modal_text": "你的反思越來越完整了，可以再加強想法之間的連結。",
    },
    "badge_90": {
        "id": "badge_90",
        "name": "松果金徽章",
        "description": "總分達到 90/90，就可以獲得。",
        "earned_description": "太棒了！你的反思內容很完整，也能連結感受、體會與行動。",
        "modal_title": "恭喜獲得松果金徽章！",
        "modal_text": "太棒了！你的反思內容很完整，也能連結感受、體會與行動。",
    },
}

BADGE_ORDER = ["badge_start", "badge_30", "badge_60", "badge_90"]


# ---------------------------------------------------------------------------
# Pure badge logic (no DB)
# ---------------------------------------------------------------------------


def calculate_earned_badges(
    *,
    has_writing_content: bool,
    has_used_feedback_or_prompt: bool,
    total_score: Optional[int],
) -> list[str]:
    """Return list of badge IDs earned given current state."""
    earned: list[str] = []

    if has_writing_content and has_used_feedback_or_prompt:
        earned.append("badge_start")

    if total_score is not None:
        if total_score >= 30:
            earned.append("badge_30")
        if total_score >= 60:
            earned.append("badge_60")
        if total_score >= 90:
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
