"""ORID badge rules and event persistence service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OridBadgeEvent
from app.content.synthesis_rubric import synthesis_badges_from_levels
from app.services.orid_rubric_scoring import parse_level
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
    "badge_synthesis_content": {
        "id": "badge_synthesis_content",
        "name": "內容整合章",
        "description": "故事事件、感受或想法、體會與未來行動彼此有關，達到整合寫作 rubric 第 3 級。",
        "earned_description": "已獲得：你已經把故事、想法、體會與行動放進同一篇文章！",
        "modal_title": "恭喜獲得內容整合章！",
        "modal_text": "你已經把故事事件、自己的想法、學到的體會和未來行動整合起來了。",
    },
    "badge_synthesis_coherence": {
        "id": "badge_synthesis_coherence",
        "name": "文章連貫章",
        "description": "內容順序合理，前後句和各部分關係清楚，達到整合寫作 rubric 第 3 級。",
        "earned_description": "已獲得：讀者可以順著你的文章讀懂前後關係！",
        "modal_title": "恭喜獲得文章連貫章！",
        "modal_text": "你的文章順序清楚，故事、感受、體會和行動能自然接起來。",
    },
    "badge_synthesis_reflection": {
        "id": "badge_synthesis_reflection",
        "name": "反思深度章",
        "description": "不只重述故事，也能說明感受、想法或學習的原因，達到整合寫作 rubric 第 3 級。",
        "earned_description": "已獲得：你不只說發生什麼，也說清楚自己為什麼這樣想！",
        "modal_title": "恭喜獲得反思深度章！",
        "modal_text": "你能用故事裡的事情說明自己的感受、想法或學習原因。",
    },
    "badge_synthesis_action": {
        "id": "badge_synthesis_action",
        "name": "行動應用章",
        "description": "提出自己能做到、具體可行且呼應體會的行動，達到整合寫作 rubric 第 3 級。",
        "earned_description": "已獲得：你已經把學到的事變成自己能做到的行動！",
        "modal_title": "恭喜獲得行動應用章！",
        "modal_text": "你提出了一個具體、可行，而且能呼應故事體會的行動。",
    },
}

BADGE_ORDER = [
    "badge_start",
    "badge_30",
    "badge_60",
    "badge_90",
    "badge_synthesis_content",
    "badge_synthesis_coherence",
    "badge_synthesis_reflection",
    "badge_synthesis_action",
]

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


def stages_passed_from_writing_obj(
    writing_obj: dict | None, *, mode: str = "ok"
) -> set[str]:
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
) -> list[str]:
    """Return badge IDs earned from start action + ORID stage progress.

    Badge IDs remain badge_30/60/90 for storage/UI assets, but unlock by:
      badge_30 (銅): O passed
      badge_60 (銀): O+R+I passed
      badge_90 (金): O+R+I+D passed
    """
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


def calculate_earned_synthesis_badges(
    *, rubric_levels: dict[str, object] | None
) -> list[str]:
    """Return one even-week badge per criterion whose level is at least 3."""
    return synthesis_badges_from_levels(rubric_levels)


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


async def load_session_progress(
    db: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    week: int,
    writing_content: str | None = None,
    empty_writing_factory,
) -> dict:
    """Return earned badges for a user session/week."""
    earned = await get_earned_badges_from_db(
        db, user_id=user_id, session_id=session_id, week=week
    )

    if writing_content:
        obj = ensure_orid_writing_obj(
            raw_content=writing_content,
            week=week,
            empty_factory=empty_writing_factory,
        )
        writing_badges = obj.get("earnedBadges")
        if isinstance(writing_badges, list):
            earned = list(set(earned + [str(b) for b in writing_badges if b]))

    return {
        "earnedBadges": earned,
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
