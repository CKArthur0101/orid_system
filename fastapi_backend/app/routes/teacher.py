from __future__ import annotations

import csv
import io
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_, cast, Integer

from app.database import get_async_session
from app.models import (
    User,
    ClassRoom,
    TeacherClassAssignment,
    StudentClassMembership,
    Reading,
    OridSession,
    OridMessage,
    OridWriting,
    OridFeedbackEvent,
    OridPostTestScore,
)
from app.schemas import (
    TeacherClassRead,
    TeacherClassOverview,
    TeacherStudentRow,
    TeacherStudentSummary,
    PostTestScoreUpsert,
    PostTestScoreRead,
)
from app.users import current_active_user

router = APIRouter(tags=["teacher"])

READING_TITLE_TEMPLATE = "第 {week} 週（暫定教材）"


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
        d2 = str(stage_obj.get("d2", "")).strip() if isinstance(stage_obj, dict) else ""
        if d1 or d2:
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
        d2 = str(stage_obj.get("d2", "")).strip() if isinstance(stage_obj, dict) else ""
        if d1 or d2:
            result.append(stage)
    return result


@router.get("/me/classes", response_model=list[TeacherClassRead])
async def teacher_me_classes(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    class_ids = await _get_allowed_class_ids(db, user)
    if not class_ids:
        return []
    q = await db.execute(select(ClassRoom).where(ClassRoom.id.in_(class_ids)).order_by(ClassRoom.name.asc()))
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
            stage_distribution={"O": 0, "R": 0, "I": 0, "D": 0},
            students=[],
        )

    student_ids = [s.id for s in students]
    reading_title = READING_TITLE_TEMPLATE.format(week=week)

    # ── 2. Latest session per student ────────────────────────────────────────
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
        .join(Reading, OridSession.reading_id == Reading.id)
        .where(
            OridSession.user_id.in_(student_ids),
            Reading.title == reading_title,
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

    # ── 3. Message counts per session ────────────────────────────────────────
    msg_counts: dict[UUID, int] = {}
    last_activity: dict[UUID, object] = {}
    if session_ids:
        mc_res = await db.execute(
            select(
                OridMessage.session_id,
                func.count(OridMessage.id).label("cnt"),
                func.max(OridMessage.created_at).label("last_at"),
            )
            .where(OridMessage.session_id.in_(session_ids))
            .group_by(OridMessage.session_id)
        )
        for mc_row in mc_res.mappings().all():
            msg_counts[mc_row["session_id"]] = int(mc_row["cnt"])
            last_activity[mc_row["session_id"]] = mc_row["last_at"]

    # ── 4. Writing completion per student ────────────────────────────────────
    writing_stages: dict[UUID, int] = {}
    if session_ids:
        wsubq = (
            select(
                OridWriting,
                func.row_number()
                .over(
                    partition_by=OridWriting.user_id,
                    order_by=OridWriting.created_at.desc(),
                )
                .label("rn"),
            )
            .where(
                OridWriting.user_id.in_(student_ids),
                OridWriting.session_id.in_(session_ids),
                OridWriting.week == week,
            )
            .subquery()
        )
        w_res = await db.execute(select(wsubq).where(wsubq.c.rn == 1))
        for w_row in w_res.mappings().all():
            uid = w_row["user_id"]
            writing_stages[uid] = _count_completed_stages(w_row.get("content"))

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
            )
            .where(OridFeedbackEvent.session_id.in_(session_ids))
            .group_by(OridFeedbackEvent.user_id)
        )
        for fb_row in fb_res.mappings().all():
            uid = fb_row["user_id"]
            feedback_clicks[uid] = int(fb_row["clicks"] or 0)
            feedback_ok_counts[uid] = int(fb_row["ok_cnt"] or 0)

        ok_stages_res = await db.execute(
            select(
                OridFeedbackEvent.user_id,
                func.count(OridFeedbackEvent.stage.distinct()).label("ok_stage_cnt"),
            )
            .where(
                OridFeedbackEvent.session_id.in_(session_ids),
                OridFeedbackEvent.ok == True,  # noqa: E712
            )
            .group_by(OridFeedbackEvent.user_id)
        )
        for os_row in ok_stages_res.mappings().all():
            feedback_ok_stages[os_row["user_id"]] = int(os_row["ok_stage_cnt"] or 0)

    # ── 6. Assemble rows ──────────────────────────────────────────────────────
    stage_distribution = {"NOT_STARTED": 0, "O": 0, "R": 0, "I": 0, "D": 0}
    rows: list[TeacherStudentRow] = []

    for student in students:
        sess = session_by_student.get(student.id)
        sid = sess["id"] if sess else None
        interaction_count = msg_counts.get(sid, 0) if sid else 0
        stage = (sess["current_stage"] if sess else "NOT_STARTED") or "NOT_STARTED"
        if interaction_count <= 0:
            stage = "NOT_STARTED"
        stage = stage if stage in stage_distribution else "NOT_STARTED"
        stage_distribution[stage] += 1

        rows.append(
            TeacherStudentRow(
                student_id=student.id,
                student_email=student.email,
                current_stage=stage,
                interaction_count=interaction_count,
                writing_completed_stages=writing_stages.get(student.id, 0),
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

    reading_title = READING_TITLE_TEMPLATE.format(week=week)
    s_res = await db.execute(
        select(OridSession)
        .join(Reading, OridSession.reading_id == Reading.id)
        .where(OridSession.user_id == student_id, Reading.title == reading_title)
        .order_by(OridSession.created_at.desc())
        .limit(1)
    )
    session = s_res.scalars().first()

    stage = (session.current_stage if session else "NOT_STARTED") or "NOT_STARTED"
    interaction_count = 0
    writing_completed_stages = 0
    stages_with_draft_list: list[str] = []
    last_activity_at = None
    feedback_click_count = 0
    feedback_ok_count = 0
    feedback_ok_stages = 0

    if session:
        mc_res = await db.execute(
            select(
                func.count(OridMessage.id).label("cnt"),
                func.max(OridMessage.created_at).label("last_at"),
            ).where(OridMessage.session_id == session.id)
        )
        mc_row = mc_res.mappings().first()
        if mc_row:
            interaction_count = int(mc_row["cnt"] or 0)
            last_activity_at = mc_row["last_at"]
        if interaction_count <= 0:
            stage = "NOT_STARTED"

        writing_res = await db.execute(
            select(OridWriting)
            .where(
                OridWriting.user_id == student_id,
                OridWriting.session_id == session.id,
                OridWriting.week == week,
            )
            .order_by(OridWriting.created_at.desc())
            .limit(1)
        )
        writing = writing_res.scalars().first()
        writing_content = writing.content if writing else None
        writing_completed_stages = _count_completed_stages(writing_content)
        stages_with_draft_list = _stages_with_draft(writing_content)

        # Feedback analytics from analytics tables
        fb_res = await db.execute(
            select(
                func.count(OridFeedbackEvent.id).label("clicks"),
            ).where(OridFeedbackEvent.session_id == session.id)
        )
        fb_row = fb_res.mappings().first()
        feedback_click_count = int((fb_row["clicks"] if fb_row else None) or 0)

        fb_ok_res = await db.execute(
            select(
                func.count(OridFeedbackEvent.id).label("ok_cnt"),
            ).where(
                OridFeedbackEvent.session_id == session.id,
                OridFeedbackEvent.ok == True,  # noqa: E712
            )
        )
        fb_ok_row = fb_ok_res.mappings().first()
        feedback_ok_count = int((fb_ok_row["ok_cnt"] if fb_ok_row else None) or 0)

        ok_stages_res = await db.execute(
            select(
                func.count(OridFeedbackEvent.stage.distinct()).label("ok_stage_cnt"),
            ).where(
                OridFeedbackEvent.session_id == session.id,
                OridFeedbackEvent.ok == True,  # noqa: E712
            )
        )
        os_row = ok_stages_res.mappings().first()
        feedback_ok_stages = int((os_row["ok_stage_cnt"] if os_row else None) or 0)

    return TeacherStudentSummary(
        class_id=class_id,
        student_id=student_id,
        student_email=student.email,
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

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "學生信箱", "目前階段", "互動次數",
        "寫作完成格數", "回饋點擊次數", "回饋通過次數", "回饋通過格數",
        "後測_O", "後測_R", "後測_I", "後測_D", "後測_ALL",
    ])
    for row in overview.students:
        uid = row.student_id
        pts = pt_by_student.get(uid, {})
        writer.writerow([
            row.student_email,
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
        ])

    output.seek(0)
    filename = f"class_{classroom.name}_week{week}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
