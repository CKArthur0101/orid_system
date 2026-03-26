from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

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
)
from app.schemas import (
    TeacherClassRead,
    TeacherClassOverview,
    TeacherStudentRow,
    TeacherStudentSummary,
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

    student_rows = await db.execute(
        select(User)
        .join(StudentClassMembership, StudentClassMembership.student_id == User.id)
        .where(StudentClassMembership.class_id == class_id)
        .order_by(User.email.asc())
    )
    students = student_rows.scalars().all()
    reading_title = READING_TITLE_TEMPLATE.format(week=week)
    stage_distribution = {"O": 0, "R": 0, "I": 0, "D": 0}
    rows: list[TeacherStudentRow] = []

    for student in students:
        s_res = await db.execute(
            select(OridSession)
            .join(Reading, OridSession.reading_id == Reading.id)
            .where(OridSession.user_id == student.id, Reading.title == reading_title)
            .order_by(OridSession.created_at.desc())
            .limit(1)
        )
        session = s_res.scalars().first()
        stage = (session.current_stage if session else "O") or "O"
        stage = stage if stage in stage_distribution else "O"
        stage_distribution[stage] += 1

        interaction_count = 0
        last_activity_at = None
        writing_completed_stages = 0

        if session:
            msg_count_res = await db.execute(
                select(func.count(OridMessage.id)).where(OridMessage.session_id == session.id)
            )
            interaction_count = int(msg_count_res.scalar() or 0)

            last_activity_res = await db.execute(
                select(func.max(OridMessage.created_at)).where(OridMessage.session_id == session.id)
            )
            last_activity_at = last_activity_res.scalar()

            writing_res = await db.execute(
                select(OridWriting)
                .where(
                    OridWriting.user_id == student.id,
                    OridWriting.session_id == session.id,
                    OridWriting.week == week,
                )
                .order_by(OridWriting.created_at.desc())
                .limit(1)
            )
            writing = writing_res.scalars().first()
            writing_completed_stages = _count_completed_stages(writing.content if writing else None)

        rows.append(
            TeacherStudentRow(
                student_id=student.id,
                student_email=student.email,
                current_stage=stage,
                interaction_count=interaction_count,
                writing_completed_stages=writing_completed_stages,
                last_activity_at=last_activity_at,
            )
        )

    total_students = len(rows)
    active_students = sum(1 for r in rows if r.interaction_count > 0)
    completed_students = sum(1 for r in rows if r.writing_completed_stages >= 4)
    completion_rate = (completed_students / total_students) if total_students else 0.0

    return TeacherClassOverview(
        class_id=classroom.id,
        class_name=classroom.name,
        week=week,
        total_students=total_students,
        active_students=active_students,
        completion_rate=round(completion_rate, 4),
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

    stage = (session.current_stage if session else "O") or "O"
    interaction_count = 0
    writing_completed_stages = 0
    last_activity_at = None

    if session:
        msg_count_res = await db.execute(
            select(func.count(OridMessage.id)).where(OridMessage.session_id == session.id)
        )
        interaction_count = int(msg_count_res.scalar() or 0)

        last_activity_res = await db.execute(
            select(func.max(OridMessage.created_at)).where(OridMessage.session_id == session.id)
        )
        last_activity_at = last_activity_res.scalar()

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
        writing_completed_stages = _count_completed_stages(writing.content if writing else None)

    return TeacherStudentSummary(
        class_id=class_id,
        student_id=student_id,
        student_email=student.email,
        week=week,
        current_stage=stage,
        interaction_count=interaction_count,
        writing_completed_stages=writing_completed_stages,
        last_activity_at=last_activity_at,
    )
