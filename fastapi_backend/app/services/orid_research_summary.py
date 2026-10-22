"""Research summary upsert service for the ORID Teacher Research MVP.

Single write entry point for `OridWeeklyResearchSummary`. This is a coarse
per-(user, week, session) counters table for the teacher research dashboard —
NOT a clickstream/event log and NOT semantic analysis of chat content.

Every public function here is best-effort: it wraps its own DB work in a
SAVEPOINT (`db.begin_nested`) and swallows/logs exceptions, so a failure to
update research counters never blocks the primary student-facing response.
Callers still own the outer transaction and must call `db.commit()`.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.week_plan import is_synthesis_week
from app.content.week_plan import task_type_for_week as _plan_task_type_for_week
from app.content.week_plan import writable_stages
from app.models import OridWeeklyResearchSummary, StudentClassMembership, User

logger = logging.getLogger(__name__)

_STAGE_KEYS = ("O", "R", "I", "D")


def normalize_writing_text(text: Optional[str]) -> str:
    """Whitespace-stripped text, used consistently for word_count and the
    revision-detection fingerprint (mirrors the existing dual-write word_count
    convention in routes/orid.py)."""
    return re.sub(r"\s+", "", text or "")


def task_type_for_week(week: int) -> str:
    return _plan_task_type_for_week(week)


def _stage_texts(writing_obj: dict | None, week: int | None = None) -> list[str]:
    """Normalized `d1` text per stage, limited to the stages this week may write.

    Week 1 counts only O/R and week 2 only I/D, so a stray copy of another
    week's text can never inflate this week's counters.
    """
    if not isinstance(writing_obj, dict):
        return []
    stages = writing_obj.get("stages")
    if not isinstance(stages, dict):
        return []
    allowed = set(writable_stages(week)) if week is not None else set()
    if not allowed:
        allowed = set(_STAGE_KEYS)
    out: list[str] = []
    for key in _STAGE_KEYS:
        if key not in allowed:
            continue
        stage_obj = stages.get(key)
        text = stage_obj.get("d1") if isinstance(stage_obj, dict) else ""
        out.append(normalize_writing_text(str(text or "")))
    return out


def compute_word_count(writing_obj: dict | None, week: int) -> int:
    """Character count (whitespace-normalized) of this week's writing text.

    ORID weeks: the `d1` fields this week may write. Integration weeks: the
    `synthesis_draft`. Chat messages are never counted (no clickstream or
    semantic analysis).
    """
    if is_synthesis_week(week):
        if not isinstance(writing_obj, dict):
            return 0
        return len(normalize_writing_text(str(writing_obj.get("synthesis_draft") or "")))
    return sum(len(t) for t in _stage_texts(writing_obj, week))


def compute_content_fingerprint(writing_obj: dict | None, week: int) -> str:
    """Hash of the concatenated normalized text, used only to detect whether
    the student's saved content changed since the last save (revision_count).
    Never exposed via API/CSV."""
    if is_synthesis_week(week):
        parts = [
            normalize_writing_text(str(writing_obj.get("synthesis_draft") or ""))
            if isinstance(writing_obj, dict)
            else ""
        ]
    else:
        parts = _stage_texts(writing_obj, week)
    source = "|".join(parts)
    return hashlib.sha1(source.encode("utf-8")).hexdigest()


async def resolve_class_id(db: AsyncSession, user_id: UUID) -> Optional[UUID]:
    """Student's earliest class membership (if multiple, first joined)."""
    res = await db.execute(
        select(StudentClassMembership.class_id)
        .where(StudentClassMembership.student_id == user_id)
        .order_by(StudentClassMembership.created_at.asc())
        .limit(1)
    )
    return res.scalars().first()


async def _resolve_condition(db: AsyncSession, user_id: UUID) -> str:
    res = await db.execute(select(User.orid_condition).where(User.id == user_id))
    condition = res.scalars().first()
    return str(condition or "experimental")


async def get_or_create_summary(
    db: AsyncSession,
    *,
    user_id: UUID,
    week: int,
    session_id: UUID,
) -> OridWeeklyResearchSummary:
    """Fetch the (user, week, session) research summary row, creating it if needed.

    `condition` / `class_id` / `task_type` are snapshotted only at creation time —
    a later change to a student's group assignment does not rewrite historical
    rows (standard research practice).
    """
    stmt = select(OridWeeklyResearchSummary).where(
        OridWeeklyResearchSummary.user_id == user_id,
        OridWeeklyResearchSummary.week == week,
        OridWeeklyResearchSummary.session_id == session_id,
    )
    row = (await db.execute(stmt)).scalars().first()
    if row is not None:
        return row

    class_id = await resolve_class_id(db, user_id)
    condition = await _resolve_condition(db, user_id)
    row = OridWeeklyResearchSummary(
        user_id=user_id,
        week=week,
        session_id=session_id,
        class_id=class_id,
        condition=condition,
        task_type=task_type_for_week(week),
    )
    db.add(row)
    try:
        async with db.begin_nested():
            await db.flush()
        return row
    except IntegrityError:
        # Concurrent insert won the race — fetch the row it created.
        existing = (await db.execute(stmt)).scalars().first()
        if existing is None:
            raise
        return existing


async def bump_save_and_maybe_revision(
    db: AsyncSession,
    *,
    user_id: UUID,
    week: int,
    session_id: UUID,
    writing_obj: dict[str, Any] | None,
) -> None:
    """Call on every writing save (draft or submit).

    Always bumps `save_count` and refreshes `word_count`. Bumps
    `revision_count` only when the normalized full text differs from the
    fingerprint saved last time (no semantic diffing, just changed/unchanged).
    """
    try:
        async with db.begin_nested():
            summary = await get_or_create_summary(
                db, user_id=user_id, week=week, session_id=session_id
            )
            fingerprint = compute_content_fingerprint(writing_obj, week)
            if (
                summary.content_fingerprint is not None
                and fingerprint != summary.content_fingerprint
            ):
                summary.revision_count = (summary.revision_count or 0) + 1
            summary.content_fingerprint = fingerprint
            summary.word_count = compute_word_count(writing_obj, week)
            summary.save_count = (summary.save_count or 0) + 1
            await db.flush()
    except Exception:
        logger.warning(
            "research summary bump_save_and_maybe_revision failed", exc_info=True
        )


async def sync_autosave_word_count(
    db: AsyncSession,
    *,
    user_id: UUID,
    week: int,
    session_id: UUID,
    writing_obj: dict[str, Any] | None,
) -> None:
    """Refresh the latest word count without recording a student action.

    Autosave must not touch save/revision counters or the research fingerprint.
    The fingerprint remains the baseline from the last explicit draft/submit.
    """
    try:
        async with db.begin_nested():
            summary = await get_or_create_summary(
                db, user_id=user_id, week=week, session_id=session_id
            )
            summary.word_count = compute_word_count(writing_obj, week)
            await db.flush()
    except Exception:
        logger.warning("research summary sync_autosave_word_count failed", exc_info=True)


async def mark_submitted(
    db: AsyncSession,
    *,
    user_id: UUID,
    week: int,
    session_id: UUID,
) -> None:
    """Call only when the student explicitly submits (not on autosave/draft)."""
    try:
        async with db.begin_nested():
            summary = await get_or_create_summary(
                db, user_id=user_id, week=week, session_id=session_id
            )
            summary.is_submitted = True
            await db.flush()
    except Exception:
        logger.warning("research summary mark_submitted failed", exc_info=True)


async def bump_guide_use(
    db: AsyncSession,
    *,
    user_id: UUID,
    week: int,
    session_id: UUID,
    amount: int = 1,
) -> None:
    """Call once per guiding-resource use: experimental 「取得回饋」, or a
    control-group card insert / explicit prompt open. Page flips do not count.
    The control check button is a pass/fail gate and is not a guide use."""
    if amount <= 0:
        return
    try:
        async with db.begin_nested():
            summary = await get_or_create_summary(
                db, user_id=user_id, week=week, session_id=session_id
            )
            summary.guide_use_count = (summary.guide_use_count or 0) + int(amount)
            await db.flush()
    except Exception:
        logger.warning("research summary bump_guide_use failed", exc_info=True)


async def sync_badges(
    db: AsyncSession,
    *,
    user_id: UUID,
    week: int,
    session_id: UUID,
    badge_count: int,
) -> None:
    """Keep `badge_count` in sync with the number of distinct badges earned
    for this user/session/week (monotonically non-decreasing)."""
    try:
        async with db.begin_nested():
            summary = await get_or_create_summary(
                db, user_id=user_id, week=week, session_id=session_id
            )
            summary.badge_count = max(int(badge_count or 0), summary.badge_count or 0)
            await db.flush()
    except Exception:
        logger.warning("research summary sync_badges failed", exc_info=True)
