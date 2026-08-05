from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_, or_, cast, Integer, case

from app.database import get_async_session
from app.models import (
    User,
    ClassRoom,
    TeacherClassAssignment,
    StudentClassMembership,
    Reading,
    OridSession,
    OridChatMessage,
    OridWeekSubmission,
    OridFeedbackEvent,
    OridPostTestScore,
    OridBadgeEvent,
    OridWeeklyResearchSummary,
)
from app.schemas import (
    OridMessageRead,
    TeacherClassRead,
    TeacherClassOverview,
    TeacherStudentRow,
    TeacherStudentSummary,
    PostTestScoreUpsert,
    PostTestScoreRead,
    TeacherResearchOverview,
    ResearchSummaryCards,
    ResearchGroupComparisonRow,
    ResearchWeeklyTrendPoint,
    ResearchCompletionDistribution,
    ResearchStudentRow,
)
from app.users import current_active_user

router = APIRouter(tags=["teacher"])

READING_TITLE_TEMPLATE = "第 {week} 週（暫定教材）"

_ORID_SENDER_STUDENT = "student"
_ORID_SENDER_AI = "ai"


def _dialogue_rounds(st_count: int, ai_count: int) -> int:
    """一輪對話 = 學生一則 + AI 一則；以兩邊則數取小（可完整配對的輪數）。"""
    return min(max(0, st_count), max(0, ai_count))


def _student_ui_name(student: User) -> str:
    d = (student.display_name or "").strip()
    return d or student.email


def _dt_for_message_filter(dt: datetime | None) -> datetime | None:
    """OridChatMessage 為 naive UTC；OridWeekSubmission 為 aware — 查詢前統一為 naive UTC。"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _book_unit_from_week(week: int) -> int:
    return (week + 1) // 2


async def _latest_orid_session_for_student_week(
    db: AsyncSession,
    student_id: UUID,
    week: int,
) -> OridSession | None:
    """
    book_unit 共用 session 後，reading_id 會隨學生進度指到「目前週」reading，
    教師切到第 1 週查看時不可再用 join Reading.title == 第 1 週 當唯一條件。
    """
    bu = _book_unit_from_week(week)
    title = READING_TITLE_TEMPLATE.format(week=week)
    r1 = await db.execute(
        select(OridSession)
        .where(OridSession.user_id == student_id, OridSession.book_unit == bu)
        .order_by(OridSession.created_at.desc())
        .limit(1)
    )
    s = r1.scalars().first()
    if s:
        return s
    r2 = await db.execute(
        select(OridSession)
        .join(Reading, OridSession.reading_id == Reading.id)
        .where(
            OridSession.user_id == student_id,
            Reading.title == title,
        )
        .order_by(OridSession.created_at.desc())
        .limit(1)
    )
    return r2.scalars().first()


async def _week_activity_start(
    db: AsyncSession,
    session: OridSession,
    week: int,
) -> datetime | None:
    """第 week 週對話開始時間（同 book_unit session 內；week 1 為 session 建立時）。"""
    if week <= 1:
        return session.created_at

    prev_week = week - 1
    prev_sub_res = await db.execute(
        select(OridWeekSubmission).where(
            OridWeekSubmission.session_id == session.id,
            OridWeekSubmission.week == prev_week,
        )
    )
    prev_sub = prev_sub_res.scalars().first()
    if prev_sub and prev_sub.updated_at:
        return prev_sub.updated_at

    curr_sub_res = await db.execute(
        select(OridWeekSubmission).where(
            OridWeekSubmission.session_id == session.id,
            OridWeekSubmission.week == week,
        )
    )
    curr_sub = curr_sub_res.scalars().first()
    if curr_sub and curr_sub.created_at:
        last_before_res = await db.execute(
            select(func.max(OridChatMessage.created_at)).where(
                OridChatMessage.session_id == session.id,
                OridChatMessage.created_at < curr_sub.created_at,
            )
        )
        last_before = last_before_res.scalar()
        if last_before:
            return last_before

    return None


async def _week_chat_bounds(
    db: AsyncSession,
    session: OridSession,
    week: int,
) -> tuple[datetime | None, datetime | None]:
    """回傳 (lower, upper) 供篩選 OridChatMessage；lower 為 None 表示本週無可辨識對話。"""
    if week % 2 == 1:
        lower = _dt_for_message_filter(session.created_at)
        upper = None
        if week < 6:
            upper = _dt_for_message_filter(
                await _week_activity_start(db, session, week + 1)
            )
        return lower, upper

    lower = _dt_for_message_filter(await _week_activity_start(db, session, week))
    return lower, None


def _message_time_filters(
    *,
    lower: datetime | None,
    upper: datetime | None,
) -> tuple:
    if lower is None:
        return (OridChatMessage.id.is_(None),)
    clauses = [OridChatMessage.created_at >= lower]
    if upper is not None:
        clauses.append(OridChatMessage.created_at < upper)
    return tuple(clauses)


async def _session_message_stats(
    db: AsyncSession,
    session: OridSession,
    week: int,
) -> tuple[int, datetime | None]:
    """依週次時間窗計算對話輪數與最後活動時間。"""
    lower, upper = await _week_chat_bounds(db, session, week)
    if lower is None:
        return 0, None

    st_sum = func.coalesce(
        func.sum(case((OridChatMessage.sender == _ORID_SENDER_STUDENT, 1), else_=0)),
        0,
    )
    ai_sum = func.coalesce(
        func.sum(case((OridChatMessage.sender == _ORID_SENDER_AI, 1), else_=0)),
        0,
    )
    time_filters = _message_time_filters(lower=lower, upper=upper)
    mc_res = await db.execute(
        select(
            st_sum.label("st_cnt"),
            ai_sum.label("ai_cnt"),
            func.max(OridChatMessage.created_at).label("last_at"),
        )
        .where(OridChatMessage.session_id == session.id, *time_filters)
    )
    mc_row = mc_res.mappings().first()
    if not mc_row:
        return 0, None
    interaction_count = _dialogue_rounds(
        int(mc_row["st_cnt"] or 0),
        int(mc_row["ai_cnt"] or 0),
    )
    return interaction_count, mc_row["last_at"]


async def _get_allowed_class_ids(db: AsyncSession, user: User) -> set[UUID]:
    if (getattr(user, "role", "student") or "student").lower() == "admin":
        q = await db.execute(select(ClassRoom.id))
        return set(q.scalars().all())

    if (getattr(user, "role", "student") or "student").lower() != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access required")

    q = await db.execute(
        select(TeacherClassAssignment.class_id).where(TeacherClassAssignment.teacher_id == user.id)
    )
    return set(q.scalars().all())


def _count_completed_stages(content: str | None) -> int:
    if not content:
        return 0
    try:
        obj = json.loads(content)
    except Exception:
        return 0
    stages = obj.get("stages") if isinstance(obj, dict) else None
    if not isinstance(stages, dict):
        return 0
    done = 0
    for stage in ["O", "R", "I", "D"]:
        stage_obj = stages.get(stage, {})
        d1 = str(stage_obj.get("d1", "")).strip() if isinstance(stage_obj, dict) else ""
        if d1:
            done += 1
    return done


def _stages_with_draft(content: str | None) -> list[str]:
    """Return list of stage keys ("O","R","I","D") that have any draft text."""
    if not content:
        return []
    try:
        obj = json.loads(content)
    except Exception:
        return []
    stages = obj.get("stages") if isinstance(obj, dict) else None
    if not isinstance(stages, dict):
        return []
    result = []
    for stage in ["O", "R", "I", "D"]:
        stage_obj = stages.get(stage, {})
        d1 = str(stage_obj.get("d1", "")).strip() if isinstance(stage_obj, dict) else ""
        if d1:
            result.append(stage)
    return result


def _csv_bool(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return ""


def _extract_submission_research_fields(content: str | None) -> dict[str, str]:
    fields: dict[str, str] = {}
    for stage in ("O", "R", "I", "D"):
        fields[f"{stage}_text"] = ""
        fields[f"{stage}_feedback_ok"] = ""
        fields[f"{stage}_rubric_focus"] = ""
        fields[f"{stage}_rubric_level_estimate"] = ""
    # Score fields
    fields["total_score"] = ""
    fields["orid_subtotal"] = ""
    fields["sel_subtotal"] = ""
    # Badge snapshot
    fields["earned_badges"] = ""

    if not content:
        return fields
    try:
        obj = json.loads(content)
    except Exception:
        return fields
    if not isinstance(obj, dict):
        return fields

    stages = obj.get("stages")
    if isinstance(stages, dict):
        for stage in ("O", "R", "I", "D"):
            stage_obj = stages.get(stage)
            if not isinstance(stage_obj, dict):
                continue
            fields[f"{stage}_text"] = str(stage_obj.get("d1") or "").strip()
            feedback = stage_obj.get("feedback")
            if not isinstance(feedback, dict):
                continue
            d1_feedback = feedback.get("d1")
            if not isinstance(d1_feedback, dict):
                continue
            fields[f"{stage}_feedback_ok"] = _csv_bool(d1_feedback.get("ok"))
            meta = d1_feedback.get("meta")
            if isinstance(meta, dict):
                fields[f"{stage}_rubric_focus"] = str(meta.get("rubric_focus") or "").strip()
                fields[f"{stage}_rubric_level_estimate"] = str(meta.get("rubric_level_estimate") or "").strip()

    # Score snapshot from writing content
    score_snap = obj.get("score")
    if isinstance(score_snap, dict):
        if score_snap.get("totalScore") is not None:
            fields["total_score"] = str(score_snap["totalScore"])
        if score_snap.get("oridSubtotal") is not None:
            fields["orid_subtotal"] = str(score_snap["oridSubtotal"])
        if score_snap.get("selSubtotal") is not None:
            fields["sel_subtotal"] = str(score_snap["selSubtotal"])

    # Badge snapshot from writing content
    earned_badges = obj.get("earnedBadges")
    if isinstance(earned_badges, list):
        fields["earned_badges"] = "|".join(str(b) for b in earned_badges)

    return fields


_STAGE_ORDER = {"NOT_STARTED": 0, "O": 1, "R": 2, "I": 3, "D": 4}
_STAGE_BY_ORDER = {0: "NOT_STARTED", 1: "O", 2: "R", 3: "I", 4: "D"}


def _teacher_display_stage(
    *,
    interaction_count: int,
    coach_stage: str,
    writing_completed_stages: int,
) -> str:
    """
    教師列出「目前階段」欄用：session.current_stage 為教練游標可能落後，
    與草稿完成格數合併取較進的 ORID 階段，避免四格皆寫完仍顯示 O。
    （班級圖表的 stage_distribution 另依各段動筆人數計，與此不同。）
    """
    if interaction_count <= 0:
        return "NOT_STARTED"
    cs = ((coach_stage or "NOT_STARTED").strip().upper()) or "NOT_STARTED"
    if cs not in _STAGE_ORDER:
        cs = "NOT_STARTED"
    if cs == "NOT_STARTED":
        cs = "O"
    coach_i = _STAGE_ORDER[cs]
    draft_i = max(0, min(int(writing_completed_stages), 4))
    eff_i = max(coach_i, draft_i)
    return _STAGE_BY_ORDER.get(eff_i, "NOT_STARTED")


@router.get("/me/classes", response_model=list[TeacherClassRead])
async def teacher_me_classes(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    class_ids = await _get_allowed_class_ids(db, user)
    if not class_ids:
        return []
    q = await db.execute(
        select(ClassRoom)
        .where(ClassRoom.id.in_(class_ids))
        .order_by(
            case((ClassRoom.external_code == "demo", 0), else_=1),
            ClassRoom.name.asc(),
            ClassRoom.created_at.asc(),
        )
    )
    return q.scalars().all()


@router.get("/classes/{class_id}/overview", response_model=TeacherClassOverview)
async def teacher_class_overview(
    class_id: UUID,
    week: int = Query(1, ge=1, le=6),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    class_ids = await _get_allowed_class_ids(db, user)
    if class_id not in class_ids:
        raise HTTPException(status_code=403, detail="Class not assigned")

    class_row = await db.execute(select(ClassRoom).where(ClassRoom.id == class_id))
    classroom = class_row.scalars().first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")

    # ── 1. All students in class ─────────────────────────────────────────────
    student_rows = await db.execute(
        select(User)
        .join(StudentClassMembership, StudentClassMembership.student_id == User.id)
        .where(StudentClassMembership.class_id == class_id)
        .order_by(User.email.asc())
    )
    students = student_rows.scalars().all()
    if not students:
        return TeacherClassOverview(
            class_id=classroom.id,
            class_name=classroom.name,
            week=week,
            total_students=0,
            active_students=0,
            completion_rate=0.0,
            feedback_ok_rate=0.0,
            stage_distribution={"NOT_STARTED": 0, "O": 0, "R": 0, "I": 0, "D": 0},
            students=[],
        )

    student_ids = [s.id for s in students]
    reading_title = READING_TITLE_TEMPLATE.format(week=week)
    bu = _book_unit_from_week(week)

    # ── 2. Latest session per student（book_unit 優先；舊資料 fallback title）──
    subq = (
        select(
            OridSession,
            func.row_number()
            .over(
                partition_by=OridSession.user_id,
                order_by=OridSession.created_at.desc(),
            )
            .label("rn"),
        )
        .outerjoin(Reading, OridSession.reading_id == Reading.id)
        .where(
            OridSession.user_id.in_(student_ids),
            or_(
                OridSession.book_unit == bu,
                and_(
                    OridSession.book_unit.is_(None),
                    Reading.title == reading_title,
                ),
            ),
        )
        .subquery()
    )
    latest_sessions_res = await db.execute(select(subq).where(subq.c.rn == 1))
    session_rows = latest_sessions_res.mappings().all()

    session_by_student: dict[UUID, dict] = {}
    session_ids: list[UUID] = []
    for row in session_rows:
        uid = row["user_id"]
        sid = row["id"]
        session_by_student[uid] = {"id": sid, "current_stage": row["current_stage"] or "O"}
        session_ids.append(sid)

    # ── 3. 對話輪數 per session（依週次時間窗；一輪 = 學生一則 + AI 一則）──
    msg_counts: dict[UUID, int] = {}
    last_activity: dict[UUID, object] = {}
    sessions_by_id: dict[UUID, OridSession] = {}
    if session_ids:
        sess_res = await db.execute(select(OridSession).where(OridSession.id.in_(session_ids)))
        for sess in sess_res.scalars().all():
            sessions_by_id[sess.id] = sess
        for sid in session_ids:
            sess = sessions_by_id.get(sid)
            if not sess:
                continue
            rounds, last_at = await _session_message_stats(db, sess, week)
            msg_counts[sid] = rounds
            last_activity[sid] = last_at

    # ── 4. Writing completion + draft presence per stage (per student) ────────
    writing_stages: dict[UUID, int] = {}
    draft_stages_by_student: dict[UUID, list[str]] = {}
    if session_ids:
        w_res = await db.execute(
            select(OridWeekSubmission).where(
                OridWeekSubmission.user_id.in_(student_ids),
                OridWeekSubmission.session_id.in_(session_ids),
                OridWeekSubmission.week == week,
            )
        )
        for row in w_res.scalars().all():
            uid = row.user_id
            writing_stages[uid] = _count_completed_stages(row.content)
            draft_stages_by_student[uid] = _stages_with_draft(row.content)

    # ── 5. Feedback analytics per student (from orid_feedback_events) ────────
    # click_count = total events; ok_count = events where ok=true;
    # ok_stages = distinct stages with ≥1 ok event
    feedback_clicks: dict[UUID, int] = {}
    feedback_ok_counts: dict[UUID, int] = {}
    feedback_ok_stages: dict[UUID, int] = {}
    if session_ids:
        fb_res = await db.execute(
            select(
                OridFeedbackEvent.user_id,
                func.count(OridFeedbackEvent.id).label("clicks"),
                func.sum(cast(OridFeedbackEvent.ok, Integer)).label("ok_cnt"),
                func.count(
                    func.distinct(
                        case((OridFeedbackEvent.ok == True, OridFeedbackEvent.stage), else_=None)  # noqa: E712
                    )
                ).label("ok_stage_cnt"),
            )
            .where(OridFeedbackEvent.session_id.in_(session_ids))
            .group_by(OridFeedbackEvent.user_id)
        )
        for fb_row in fb_res.mappings().all():
            uid = fb_row["user_id"]
            feedback_clicks[uid] = int(fb_row["clicks"] or 0)
            feedback_ok_counts[uid] = int(fb_row["ok_cnt"] or 0)
            feedback_ok_stages[uid] = int(fb_row["ok_stage_cnt"] or 0)

    # ── 6. 各段「曾動筆」人數（可重疊；寫齊四段者同時計入 O～D）──────────────
    stage_distribution = {"NOT_STARTED": 0, "O": 0, "R": 0, "I": 0, "D": 0}
    for student in students:
        keys_list = draft_stages_by_student.get(student.id, [])
        if not keys_list:
            stage_distribution["NOT_STARTED"] += 1
        else:
            for st in ("O", "R", "I", "D"):
                if st in keys_list:
                    stage_distribution[st] += 1

    # ── 7. Assemble rows ───────────────────────────────────────────────────────
    valid_row_stages = {"NOT_STARTED", "O", "R", "I", "D"}
    rows: list[TeacherStudentRow] = []

    for student in students:
        sess = session_by_student.get(student.id)
        sid = sess["id"] if sess else None
        interaction_count = msg_counts.get(sid, 0) if sid else 0
        coach_stage = (sess["current_stage"] if sess else "NOT_STARTED") or "NOT_STARTED"
        w_done = writing_stages.get(student.id, 0)
        stage = _teacher_display_stage(
            interaction_count=interaction_count,
            coach_stage=coach_stage,
            writing_completed_stages=w_done,
        )
        stage = stage if stage in valid_row_stages else "NOT_STARTED"

        rows.append(
            TeacherStudentRow(
                student_id=student.id,
                student_email=student.email,
                student_display_name=_student_ui_name(student),
                current_stage=stage,
                interaction_count=interaction_count,
                writing_completed_stages=w_done,
                last_activity_at=last_activity.get(sid) if sid else None,
                feedback_click_count=feedback_clicks.get(student.id, 0),
                feedback_ok_count=feedback_ok_counts.get(student.id, 0),
                feedback_ok_stages=feedback_ok_stages.get(student.id, 0),
            )
        )

    total_students = len(rows)
    active_students = sum(1 for r in rows if r.interaction_count > 0)
    completed_students = sum(1 for r in rows if r.writing_completed_stages >= 4)
    completion_rate = (completed_students / total_students) if total_students else 0.0
    fb_ok_students = sum(1 for r in rows if r.feedback_ok_stages >= 4)
    feedback_ok_rate = (fb_ok_students / total_students) if total_students else 0.0

    return TeacherClassOverview(
        class_id=classroom.id,
        class_name=classroom.name,
        week=week,
        total_students=total_students,
        active_students=active_students,
        completion_rate=round(completion_rate, 4),
        feedback_ok_rate=round(feedback_ok_rate, 4),
        stage_distribution=stage_distribution,
        students=rows,
    )


@router.get("/classes/{class_id}/students/{student_id}/summary", response_model=TeacherStudentSummary)
async def teacher_student_summary(
    class_id: UUID,
    student_id: UUID,
    week: int = Query(1, ge=1, le=6),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    class_ids = await _get_allowed_class_ids(db, user)
    if class_id not in class_ids:
        raise HTTPException(status_code=403, detail="Class not assigned")

    member = await db.execute(
        select(StudentClassMembership).where(
            StudentClassMembership.class_id == class_id,
            StudentClassMembership.student_id == student_id,
        )
    )
    if not member.scalars().first():
        raise HTTPException(status_code=404, detail="Student not in class")

    stu = await db.execute(select(User).where(User.id == student_id))
    student = stu.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    session = await _latest_orid_session_for_student_week(db, student_id, week)

    stage = (session.current_stage if session else "NOT_STARTED") or "NOT_STARTED"
    interaction_count = 0
    writing_completed_stages = 0
    stages_with_draft_list: list[str] = []
    last_activity_at = None
    feedback_click_count = 0
    feedback_ok_count = 0
    feedback_ok_stages = 0

    if session:
        interaction_count, last_activity_at = await _session_message_stats(db, session, week)
        writing_res = await db.execute(
            select(OridWeekSubmission).where(
                OridWeekSubmission.user_id == student_id,
                OridWeekSubmission.session_id == session.id,
                OridWeekSubmission.week == week,
            )
        )
        writing = writing_res.scalars().first()
        writing_content = writing.content if writing else None
        writing_completed_stages = _count_completed_stages(writing_content)
        stages_with_draft_list = _stages_with_draft(writing_content)

        # Feedback analytics from analytics tables
        fb_res = await db.execute(
            select(
                func.count(OridFeedbackEvent.id).label("clicks"),
                func.sum(cast(OridFeedbackEvent.ok, Integer)).label("ok_cnt"),
                func.count(
                    func.distinct(
                        case((OridFeedbackEvent.ok == True, OridFeedbackEvent.stage), else_=None)  # noqa: E712
                    )
                ).label("ok_stage_cnt"),
            ).where(OridFeedbackEvent.session_id == session.id)
        )
        fb_row = fb_res.mappings().first()
        feedback_click_count = int((fb_row["clicks"] if fb_row else None) or 0)
        feedback_ok_count = int((fb_row["ok_cnt"] if fb_row else None) or 0)
        feedback_ok_stages = int((fb_row["ok_stage_cnt"] if fb_row else None) or 0)

        if interaction_count <= 0:
            stage = "NOT_STARTED"
        else:
            stage = _teacher_display_stage(
                interaction_count=interaction_count,
                coach_stage=stage,
                writing_completed_stages=writing_completed_stages,
            )

    return TeacherStudentSummary(
        class_id=class_id,
        student_id=student_id,
        student_email=student.email,
        student_display_name=_student_ui_name(student),
        week=week,
        current_stage=stage,
        interaction_count=interaction_count,
        writing_completed_stages=writing_completed_stages,
        stages_with_draft=stages_with_draft_list,
        last_activity_at=last_activity_at,
        feedback_click_count=feedback_click_count,
        feedback_ok_count=feedback_ok_count,
        feedback_ok_stages=feedback_ok_stages,
    )


@router.get(
    "/classes/{class_id}/students/{student_id}/chat-messages",
    response_model=list[OridMessageRead],
)
async def teacher_student_chat_messages(
    class_id: UUID,
    student_id: UUID,
    week: int = Query(1, ge=1, le=6),
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """該週與個人摘要相同的 ORID session 之寫作教練對話紀錄（依時間正序）。"""
    class_ids = await _get_allowed_class_ids(db, user)
    if class_id not in class_ids:
        raise HTTPException(status_code=403, detail="Class not assigned")

    member = await db.execute(
        select(StudentClassMembership).where(
            StudentClassMembership.class_id == class_id,
            StudentClassMembership.student_id == student_id,
        )
    )
    if not member.scalars().first():
        raise HTTPException(status_code=404, detail="Student not in class")

    session = await _latest_orid_session_for_student_week(db, student_id, week)
    if not session:
        return []

    lower, upper = await _week_chat_bounds(db, session, week)
    if lower is None:
        return []

    time_filters = _message_time_filters(lower=lower, upper=upper)
    res = await db.execute(
        select(OridChatMessage)
        .where(OridChatMessage.session_id == session.id, *time_filters)
        .order_by(OridChatMessage.created_at.asc())
        .limit(limit)
    )
    return res.scalars().all()


# ── Post-test score endpoints ────────────────────────────────────────────────

@router.get(
    "/classes/{class_id}/students/{student_id}/post-test",
    response_model=list[PostTestScoreRead],
)
async def get_post_test_scores(
    class_id: UUID,
    student_id: UUID,
    week: int = Query(1, ge=1, le=6),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    class_ids = await _get_allowed_class_ids(db, user)
    if class_id not in class_ids:
        raise HTTPException(status_code=403, detail="Class not assigned")

    res = await db.execute(
        select(OridPostTestScore).where(
            OridPostTestScore.student_id == student_id,
            OridPostTestScore.class_id == class_id,
            OridPostTestScore.week == week,
        ).order_by(OridPostTestScore.stage)
    )
    return res.scalars().all()


@router.put(
    "/classes/{class_id}/students/{student_id}/post-test",
    response_model=PostTestScoreRead,
)
async def upsert_post_test_score(
    class_id: UUID,
    student_id: UUID,
    payload: PostTestScoreUpsert,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Create or update a single post-test score entry (student × week × stage)."""
    class_ids = await _get_allowed_class_ids(db, user)
    if class_id not in class_ids:
        raise HTTPException(status_code=403, detail="Class not assigned")

    existing_res = await db.execute(
        select(OridPostTestScore).where(
            OridPostTestScore.student_id == student_id,
            OridPostTestScore.class_id == class_id,
            OridPostTestScore.week == payload.week,
            OridPostTestScore.stage == payload.stage,
        )
    )
    existing = existing_res.scalars().first()

    if existing:
        existing.score = payload.score
        existing.max_score = payload.max_score
        existing.rubric_id = payload.rubric_id
        existing.note = payload.note
        existing.grader_id = user.id
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        new_score = OridPostTestScore(
            id=uuid4(),
            student_id=student_id,
            grader_id=user.id,
            class_id=class_id,
            week=payload.week,
            stage=payload.stage,
            rubric_id=payload.rubric_id,
            score=payload.score,
            max_score=payload.max_score,
            note=payload.note,
        )
        db.add(new_score)
        await db.commit()
        await db.refresh(new_score)
        return new_score


@router.get("/rubric")
async def get_writing_rubric(
    week: int = Query(1, ge=1, le=6),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Return the writing_rubric for the given week from the reading's book_pack.
    Used by the teacher dashboard to display scoring criteria when grading post-tests.
    """
    await _get_allowed_class_ids(db, user)  # auth check

    reading_title = READING_TITLE_TEMPLATE.format(week=week)
    r_res = await db.execute(
        select(Reading)
        .where(Reading.title == reading_title)
        .order_by(Reading.created_at.desc())
        .limit(1)
    )
    reading = r_res.scalars().first()

    rubric: dict = {}
    if reading and (reading.content or "").strip():
        try:
            from app.routes.orid import load_book_pack_from_reading
            bp = load_book_pack_from_reading(reading)
            rubric = (bp or {}).get("writing_rubric") or {}
        except Exception:
            pass

    if not rubric:
        # Fall back to in-code pack
        try:
            from app.routes.orid import BOOK_PACK_BY_WEEK
            rubric = (BOOK_PACK_BY_WEEK.get(week) or {}).get("writing_rubric") or {}
        except Exception:
            pass

    return {"week": week, "writing_rubric": rubric}


@router.get("/classes/{class_id}/export")
async def export_class_csv(
    class_id: UUID,
    week: int = Query(1, ge=1, le=6),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Download a CSV with per-student analytics and post-test scores for the given week."""
    class_ids = await _get_allowed_class_ids(db, user)
    if class_id not in class_ids:
        raise HTTPException(status_code=403, detail="Class not assigned")

    class_row = await db.execute(select(ClassRoom).where(ClassRoom.id == class_id))
    classroom = class_row.scalars().first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")

    # Reuse overview to get per-student analytics
    from app.routes.teacher import teacher_class_overview
    overview = await teacher_class_overview(class_id, week, db, user)

    # Post-test scores: fetch all for this class+week
    pts_res = await db.execute(
        select(OridPostTestScore).where(
            OridPostTestScore.class_id == class_id,
            OridPostTestScore.week == week,
        )
    )
    pt_scores_raw = pts_res.scalars().all()
    # index: student_id → stage → score
    pt_by_student: dict[UUID, dict[str, int]] = {}
    for pt in pt_scores_raw:
        pt_by_student.setdefault(pt.student_id, {})[pt.stage] = pt.score

    student_ids = [row.student_id for row in overview.students]
    submission_fields_by_student: dict[UUID, dict[str, str]] = {}
    if student_ids:
        sub_res = await db.execute(
            select(OridWeekSubmission)
            .where(
                OridWeekSubmission.user_id.in_(student_ids),
                OridWeekSubmission.week == week,
            )
            .order_by(OridWeekSubmission.updated_at.desc())
        )
        for submission in sub_res.scalars().all():
            if submission.user_id not in submission_fields_by_student:
                submission_fields_by_student[submission.user_id] = _extract_submission_research_fields(submission.content)

    # Fetch user orid_condition
    condition_by_student: dict[UUID, str] = {}
    if student_ids:
        user_res = await db.execute(select(User.id, User.orid_condition).where(User.id.in_(student_ids)))
        for uid_val, cond in user_res.all():
            condition_by_student[uid_val] = str(cond or "experimental")

    # Fetch badge events per student per week
    badge_events_by_student: dict[UUID, list[OridBadgeEvent]] = {}
    if student_ids:
        badge_res = await db.execute(
            select(OridBadgeEvent)
            .where(
                OridBadgeEvent.user_id.in_(student_ids),
                OridBadgeEvent.week == week,
            )
            .order_by(OridBadgeEvent.created_at.asc())
        )
        for evt in badge_res.scalars().all():
            badge_events_by_student.setdefault(evt.user_id, []).append(evt)

    def _badge_events_to_fields(events: list[OridBadgeEvent]) -> dict[str, str]:
        fields: dict[str, str] = {}
        badge_ids = ["badge_start", "badge_30", "badge_60", "badge_90"]
        for bid in badge_ids:
            earned_evt = next((e for e in events if e.badge_id == bid), None)
            fields[f"{bid}_earned"] = "1" if earned_evt else "0"
            fields[f"{bid}_earned_at"] = earned_evt.created_at.isoformat() if earned_evt else ""
        total_scores = [e.total_score for e in events if e.total_score is not None]
        fields["badge_max_score"] = str(max(total_scores)) if total_scores else ""
        fields["badge_feedback_count"] = str(max((e.feedback_count or 0) for e in events) if events else 0)
        fields["badge_prompt_view_count"] = str(max((e.prompt_view_count or 0) for e in events) if events else 0)
        fields["badge_word_count"] = str(max((e.word_count or 0) for e in events) if events else 0)
        return fields

    output = io.StringIO()
    writer = csv.writer(output)
    research_headers: list[str] = []
    for stage in ("O", "R", "I", "D"):
        research_headers.extend(
            [
                f"{stage}_text",
                f"{stage}_feedback_ok",
                f"{stage}_rubric_focus",
                f"{stage}_rubric_level_estimate",
            ]
        )
    badge_headers = [
        "badge_start_earned", "badge_start_earned_at",
        "badge_30_earned", "badge_30_earned_at",
        "badge_60_earned", "badge_60_earned_at",
        "badge_90_earned", "badge_90_earned_at",
        "badge_max_score", "badge_feedback_count",
        "badge_prompt_view_count", "badge_word_count",
    ]
    writer.writerow([
        "姓名", "學生信箱", "研究組別", "目前階段", "對話輪數",
        "寫作完成格數", "回饋點擊次數", "回饋通過次數", "回饋通過格數",
        "後測_O", "後測_R", "後測_I", "後測_D", "後測_ALL",
        # System AI scores are exploratory only (not formal RQ1/RQ2 DVs).
        "ai_system_total_score_exploratory", "ai_system_orid_score_exploratory",
        "ai_system_sel_score_exploratory", "earned_badges_participation",
        *research_headers,
        *badge_headers,
    ])
    for row in overview.students:
        uid = row.student_id
        pts = pt_by_student.get(uid, {})
        research_fields = submission_fields_by_student.get(uid, _extract_submission_research_fields(None))
        badge_fields = _badge_events_to_fields(badge_events_by_student.get(uid, []))
        condition_label = condition_by_student.get(uid, "experimental")
        writer.writerow([
            row.student_display_name,
            row.student_email,
            condition_label,
            row.current_stage,
            row.interaction_count,
            row.writing_completed_stages,
            row.feedback_click_count,
            row.feedback_ok_count,
            row.feedback_ok_stages,
            pts.get("O", ""),
            pts.get("R", ""),
            pts.get("I", ""),
            pts.get("D", ""),
            pts.get("ALL", ""),
            research_fields.get("total_score", ""),
            research_fields.get("orid_subtotal", ""),
            research_fields.get("sel_subtotal", ""),
            research_fields.get("earned_badges", ""),
            *(research_fields.get(h, "") for h in research_headers),
            *(badge_fields.get(h, "") for h in badge_headers),
        ])

    output.seek(0)
    filename = f"class_{classroom.name}_week{week}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Research dashboard (ORID Teacher Research MVP) ──────────────────────────
# Built on OridWeeklyResearchSummary (one row per student × week × session).
# Separate from the monitoring overview/export above — does not replace them.

def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _avg_or_none(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


async def teacher_research_overview(
    class_id: UUID,
    week: int | None,
    db: AsyncSession,
    user: User,
) -> TeacherResearchOverview:
    class_ids = await _get_allowed_class_ids(db, user)
    if class_id not in class_ids:
        raise HTTPException(status_code=403, detail="Class not assigned")

    class_row = await db.execute(select(ClassRoom).where(ClassRoom.id == class_id))
    classroom = class_row.scalars().first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")

    student_res = await db.execute(
        select(User)
        .join(StudentClassMembership, StudentClassMembership.student_id == User.id)
        .where(StudentClassMembership.class_id == class_id)
        .order_by(User.email.asc())
    )
    students = student_res.scalars().all()
    student_ids = [s.id for s in students]
    student_by_id = {s.id: s for s in students}

    if not students:
        return TeacherResearchOverview(
            class_id=classroom.id,
            class_name=classroom.name,
            week=week,
            summary_cards=ResearchSummaryCards(
                total_students=0, experimental_count=0, control_count=0,
                submitted_count=0, submission_rate=0.0, avg_guide_use_count=0.0,
                avg_total_score=None,
            ),
            group_comparison=[],
            weekly_trends=[],
            completion_distribution=ResearchCompletionDistribution(submitted=0, not_submitted=0),
            student_rows=[],
        )

    experimental_count = sum(1 for s in students if (s.orid_condition or "experimental") != "control")
    control_count = len(students) - experimental_count

    # Rows in scope for cards / group comparison / completion / student table.
    # `week=None` means "aggregated across weeks 1–6" (each student-week row is
    # one data point) — weekly_trends below always spans all 6 weeks regardless.
    scope_stmt = select(OridWeeklyResearchSummary).where(
        OridWeeklyResearchSummary.user_id.in_(student_ids)
    )
    if week is not None:
        scope_stmt = scope_stmt.where(OridWeeklyResearchSummary.week == week)
    scope_rows = (await db.execute(scope_stmt)).scalars().all()

    total_rows = len(scope_rows)
    submitted_count = sum(1 for r in scope_rows if r.is_submitted)
    total_scores = [r.total_score for r in scope_rows if r.total_score is not None]

    summary_cards = ResearchSummaryCards(
        total_students=len(students),
        experimental_count=experimental_count,
        control_count=control_count,
        submitted_count=submitted_count,
        submission_rate=round(submitted_count / total_rows, 4) if total_rows else 0.0,
        avg_guide_use_count=_avg([r.guide_use_count for r in scope_rows]),
        avg_total_score=_avg_or_none(total_scores),
    )

    group_comparison: list[ResearchGroupComparisonRow] = []
    for cond in ("experimental", "control"):
        cond_rows = [r for r in scope_rows if (r.condition or "experimental") == cond]
        cond_submitted = sum(1 for r in cond_rows if r.is_submitted)
        group_comparison.append(
            ResearchGroupComparisonRow(
                condition=cond,
                student_count=len({r.user_id for r in cond_rows}),
                avg_word_count=_avg([r.word_count for r in cond_rows]),
                avg_revision_count=_avg([r.revision_count for r in cond_rows]),
                avg_guide_use_count=_avg([r.guide_use_count for r in cond_rows]),
                avg_badge_count=_avg([r.badge_count for r in cond_rows]),
                avg_orid_score=_avg_or_none([r.orid_score for r in cond_rows if r.orid_score is not None]),
                avg_sel_score=_avg_or_none([r.sel_score for r in cond_rows if r.sel_score is not None]),
                avg_total_score=_avg_or_none([r.total_score for r in cond_rows if r.total_score is not None]),
                submission_rate=round(cond_submitted / len(cond_rows), 4) if cond_rows else 0.0,
            )
        )

    trend_res = await db.execute(
        select(OridWeeklyResearchSummary).where(OridWeeklyResearchSummary.user_id.in_(student_ids))
    )
    trend_rows = trend_res.scalars().all()
    weekly_trends: list[ResearchWeeklyTrendPoint] = []
    for wk in range(1, 7):
        for cond in ("experimental", "control"):
            rows = [r for r in trend_rows if r.week == wk and (r.condition or "experimental") == cond]
            if not rows:
                continue
            weekly_trends.append(
                ResearchWeeklyTrendPoint(
                    week=wk,
                    condition=cond,
                    avg_word_count=_avg([r.word_count for r in rows]),
                    avg_revision_count=_avg([r.revision_count for r in rows]),
                    avg_guide_use_count=_avg([r.guide_use_count for r in rows]),
                    avg_badge_count=_avg([r.badge_count for r in rows]),
                    avg_orid_score=_avg_or_none([r.orid_score for r in rows if r.orid_score is not None]),
                    avg_sel_score=_avg_or_none([r.sel_score for r in rows if r.sel_score is not None]),
                    avg_total_score=_avg_or_none([r.total_score for r in rows if r.total_score is not None]),
                    student_count=len({r.user_id for r in rows}),
                )
            )

    completion_distribution = ResearchCompletionDistribution(
        submitted=submitted_count,
        not_submitted=total_rows - submitted_count,
    )

    student_rows_out: list[ResearchStudentRow] = [
        ResearchStudentRow(
            student_id=r.user_id,
            student_email=student_by_id[r.user_id].email,
            student_display_name=_student_ui_name(student_by_id[r.user_id]),
            condition=r.condition or "experimental",
            week=r.week,
            task_type=r.task_type,
            word_count=r.word_count,
            save_count=r.save_count,
            revision_count=r.revision_count,
            guide_use_count=r.guide_use_count,
            badge_count=r.badge_count,
            orid_score=r.orid_score,
            sel_score=r.sel_score,
            total_score=r.total_score,
            is_submitted=r.is_submitted,
        )
        for r in scope_rows
        if r.user_id in student_by_id
    ]
    student_rows_out.sort(key=lambda row: (row.student_email, row.week))

    return TeacherResearchOverview(
        class_id=classroom.id,
        class_name=classroom.name,
        week=week,
        summary_cards=summary_cards,
        group_comparison=group_comparison,
        weekly_trends=weekly_trends,
        completion_distribution=completion_distribution,
        student_rows=student_rows_out,
    )


@router.get("/classes/{class_id}/research-overview", response_model=TeacherResearchOverview)
async def get_teacher_research_overview(
    class_id: UUID,
    week: int | None = Query(None, ge=1, le=6),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Research-analysis data for the "研究分析" tab: guiding-method (condition)
    vs. writing engagement/revision, built from OridWeeklyResearchSummary.
    `week` omitted → aggregated across weeks 1–6 (weekly_trends always spans
    all 6 weeks regardless, since that is its purpose)."""
    return await teacher_research_overview(class_id, week, db, user)


@router.get("/classes/{class_id}/research-export")
async def export_research_csv(
    class_id: UUID,
    week: int | None = Query(None, ge=1, le=6),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Download a research CSV (one row per student × week) for the
    "研究分析" tab. Separate from /classes/{class_id}/export (monitoring)."""
    class_ids = await _get_allowed_class_ids(db, user)
    if class_id not in class_ids:
        raise HTTPException(status_code=403, detail="Class not assigned")

    class_row = await db.execute(select(ClassRoom).where(ClassRoom.id == class_id))
    classroom = class_row.scalars().first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Class not found")

    overview = await teacher_research_overview(class_id, week, db, user)

    student_ids = [row.student_id for row in overview.student_rows]
    badges_by_student_week: dict[tuple[UUID, int], set[str]] = {}
    if student_ids:
        badge_res = await db.execute(
            select(OridBadgeEvent.user_id, OridBadgeEvent.week, OridBadgeEvent.badge_id).where(
                OridBadgeEvent.user_id.in_(student_ids)
            )
        )
        for uid, evt_week, badge_id in badge_res.all():
            try:
                wk = int(evt_week)
            except (TypeError, ValueError):
                continue
            badges_by_student_week.setdefault((uid, wk), set()).add(str(badge_id))

    def _ordered_badges(badge_ids: set[str]) -> str:
        # Odd-week participation track only in research CSV; synthesis badge
        # intentionally omitted (process badge; see research_design_context).
        order = ["badge_start", "badge_30", "badge_60", "badge_90"]
        return "|".join(b for b in order if b in badge_ids)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "student_email", "student_name", "condition", "week", "task_type",
        "word_count", "save_count", "revision_count", "guide_use_count",
        "badge_count", "earned_badges",
        # Exploratory system AI scores — NOT formal RQ1/RQ2 dependent variables.
        "ai_system_orid_score_exploratory",
        "ai_system_sel_score_exploratory",
        "ai_system_total_score_exploratory",
        "is_submitted",
    ])
    for row in overview.student_rows:
        writer.writerow([
            row.student_email,
            row.student_display_name,
            row.condition,
            row.week,
            row.task_type or "",
            row.word_count,
            row.save_count,
            row.revision_count,
            row.guide_use_count,
            row.badge_count,
            _ordered_badges(badges_by_student_week.get((row.student_id, int(row.week)), set())),
            row.orid_score if row.orid_score is not None else "",
            row.sel_score if row.sel_score is not None else "",
            row.total_score if row.total_score is not None else "",
            _csv_bool(row.is_submitted),
        ])

    output.seek(0)
    week_label = str(week) if week is not None else "all"
    filename = f"research_{classroom.name}_week{week_label}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
