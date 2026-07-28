"""Backfill `orid_weekly_research_summaries` from existing historical data.

One-time script for the ORID Teacher Research MVP: creates a best-effort
research summary row for every existing `OridWeekSubmission` (draft/submission)
so the teacher research dashboard has data for weeks recorded before the
research-summary hooks were added. New activity going forward is tracked
live by the hooks in routes/orid.py — this script never needs to run again
for that data.

Known approximations (documented, not "recoverable" from history):
  - `save_count` / `revision_count`: history has no autosave log → set to 0.
    Only NEW saves after this backfill increment them.
  - `is_submitted`: any existing `OridWeekSubmission` row is treated as
    submitted=true (conservative: it reached the server at least once).
  - `guide_use_count`: experimental ≈ count of `orid_feedback_events` for the
    session; control ≈ max `prompt_view_count` seen on that session's badge
    events. Both are session-scoped approximations (a session can span two
    calendar weeks / one "book unit"), not an exact per-week replay.
  - `badge_count`: distinct badge_id earned on that session (session-scoped,
    same caveat as above).

Usage:
  uv run python commands/backfill_orid_research_summary.py [--dry-run]
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_backend_root = Path(__file__).resolve().parents[1]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from dotenv import load_dotenv
from sqlalchemy import func, select

from app.database import async_session_maker
from app.models import (
    OridBadgeEvent,
    OridFeedbackEvent,
    OridWeekSubmission,
    OridWeeklyResearchSummary,
    User,
)
from app.services.orid_research_summary import (
    compute_content_fingerprint,
    compute_word_count,
    resolve_class_id,
    task_type_for_week,
)
from app.services.orid_rubric_scoring import calculate_orid_sel_score, collect_levels_from_writing_obj
from app.services.orid_writing_store import ensure_orid_writing_obj

load_dotenv()


def _empty_writing_v1(week: int) -> dict:
    return {
        "schema": "orid_writing_v1",
        "week": week,
        "stages": {k: {"d1": "", "d2": ""} for k in ("O", "R", "I", "D")},
    }


def _score_from_writing_obj(obj: dict) -> tuple[float | None, float | None, int | None]:
    score_snap = obj.get("score")
    if isinstance(score_snap, dict) and score_snap.get("totalScore") is not None:
        try:
            return (
                score_snap.get("oridSubtotal"),
                score_snap.get("selSubtotal"),
                int(score_snap["totalScore"]),
            )
        except (TypeError, ValueError):
            pass
    orid_levels, sel_levels = collect_levels_from_writing_obj(obj)
    if not orid_levels and not sel_levels:
        return None, None, None
    result = calculate_orid_sel_score(orid_levels, sel_levels)
    return result.get("oridSubtotal"), result.get("selSubtotal"), result.get("totalScore")


async def main(dry_run: bool = False) -> None:
    async with async_session_maker() as db:
        submissions = (await db.execute(select(OridWeekSubmission))).scalars().all()
        print(f"[backfill] {len(submissions)} existing OridWeekSubmission rows found")

        # Cache per-user condition/class_id lookups.
        condition_cache: dict = {}
        class_id_cache: dict = {}
        created = 0
        skipped = 0

        for sub in submissions:
            key = (sub.user_id, sub.week, sub.session_id)
            existing = (
                await db.execute(
                    select(OridWeeklyResearchSummary).where(
                        OridWeeklyResearchSummary.user_id == sub.user_id,
                        OridWeeklyResearchSummary.week == sub.week,
                        OridWeeklyResearchSummary.session_id == sub.session_id,
                    )
                )
            ).scalars().first()
            if existing is not None:
                skipped += 1
                continue

            writing_obj = ensure_orid_writing_obj(
                raw_content=sub.content,
                week=sub.week,
                empty_factory=_empty_writing_v1,
            )
            word_count = compute_word_count(writing_obj, sub.week)
            orid_score, sel_score, total_score = _score_from_writing_obj(writing_obj)

            if sub.user_id not in condition_cache:
                cond_res = await db.execute(select(User.orid_condition).where(User.id == sub.user_id))
                condition_cache[sub.user_id] = str(cond_res.scalars().first() or "experimental")
            condition = condition_cache[sub.user_id]

            if sub.user_id not in class_id_cache:
                class_id_cache[sub.user_id] = await resolve_class_id(db, sub.user_id)
            class_id = class_id_cache[sub.user_id]

            badge_events = (
                await db.execute(
                    select(OridBadgeEvent).where(
                        OridBadgeEvent.user_id == sub.user_id,
                        OridBadgeEvent.session_id == sub.session_id,
                    )
                )
            ).scalars().all()
            badge_count = len({e.badge_id for e in badge_events})

            guide_use_count = 0
            if condition == "control":
                prompt_counts = [e.prompt_view_count or 0 for e in badge_events]
                guide_use_count = max(prompt_counts) if prompt_counts else 0
            else:
                fb_count_res = await db.execute(
                    select(func.count(OridFeedbackEvent.id)).where(
                        OridFeedbackEvent.user_id == sub.user_id,
                        OridFeedbackEvent.session_id == sub.session_id,
                    )
                )
                guide_use_count = int(fb_count_res.scalar() or 0)

            row = OridWeeklyResearchSummary(
                user_id=sub.user_id,
                week=sub.week,
                session_id=sub.session_id,
                class_id=class_id,
                condition=condition,
                task_type=task_type_for_week(sub.week),
                word_count=word_count,
                save_count=0,
                revision_count=0,
                guide_use_count=guide_use_count,
                badge_count=badge_count,
                orid_score=orid_score,
                sel_score=sel_score,
                total_score=total_score,
                is_submitted=True,
                content_fingerprint=compute_content_fingerprint(writing_obj, sub.week),
            )
            if dry_run:
                print(f"[dry-run] would create summary for {key}: word_count={word_count} "
                      f"guide_use={guide_use_count} badges={badge_count} total_score={total_score}")
            else:
                db.add(row)
            created += 1

        if not dry_run:
            await db.commit()
        print(f"[backfill] created={created} skipped(existing)={skipped} dry_run={dry_run}")


if __name__ == "__main__":
    asyncio.run(main(dry_run="--dry-run" in sys.argv))
