"""教師儀表板：同 book_unit session 內依週次切分對話。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi_users.password import PasswordHelper

from app.models import (
    ClassRoom,
    OridChatMessage,
    OridSession,
    OridWeekSubmission,
    Reading,
    StudentClassMembership,
    TeacherClassAssignment,
    User,
)
from app.routes.teacher import (
    _session_message_stats,
    _week_chat_bounds,
)
from app.users import get_jwt_strategy


@pytest.fixture
async def teacher_setup(db_session):
    ph = PasswordHelper()
    teacher = User(
        id=uuid.uuid4(),
        email="teacher_week@test.local",
        hashed_password=ph.hash("TeacherPass1"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="teacher",
        display_name="週次教師",
    )
    student = User(
        id=uuid.uuid4(),
        email="student_week@test.local",
        hashed_password=ph.hash("StudentPass1"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="student",
        display_name="週次學生",
    )
    classroom = ClassRoom(name="週次班", year=2026, external_code="week-class")
    reading_w1 = Reading(title="第 1 週（暫定教材）", content="{}")
    reading_w2 = Reading(title="第 2 週（暫定教材）", content="{}")
    db_session.add_all([teacher, student, classroom, reading_w1, reading_w2])
    await db_session.flush()

    db_session.add_all(
        [
            TeacherClassAssignment(teacher_id=teacher.id, class_id=classroom.id),
            StudentClassMembership(student_id=student.id, class_id=classroom.id),
        ]
    )

    base = datetime(2026, 5, 1, 10, 0, 0)
    session = OridSession(
        id=uuid.uuid4(),
        user_id=student.id,
        reading_id=reading_w2.id,
        current_stage="O",
        book_unit=1,
        created_at=base,
    )
    db_session.add(session)
    await db_session.flush()

    week1_msgs = [
        (base + timedelta(minutes=1), "student", "w1 student"),
        (base + timedelta(minutes=2), "ai", "w1 ai"),
    ]
    week2_msgs = [
        (base + timedelta(hours=2), "student", "w2 student"),
        (base + timedelta(hours=3), "ai", "w2 ai"),
    ]
    for at, sender, text in week1_msgs + week2_msgs:
        db_session.add(
            OridChatMessage(
                id=uuid.uuid4(),
                session_id=session.id,
                stage="O",
                sender=sender,
                text=text,
                created_at=at,
            )
        )

    w1_sub = OridWeekSubmission(
        id=uuid.uuid4(),
        user_id=student.id,
        reading_id=reading_w1.id,
        session_id=session.id,
        week=1,
        content='{"stages":{"O":{"d1":"x"}}}',
        created_at=base + timedelta(minutes=30),
        updated_at=base + timedelta(minutes=45),
    )
    db_session.add(w1_sub)
    await db_session.commit()
    await db_session.refresh(session)

    token = await get_jwt_strategy().write_token(teacher)
    return {
        "teacher_headers": {"Authorization": f"Bearer {token}"},
        "classroom": classroom,
        "student": student,
        "session": session,
        "week1_texts": {m[2] for m in week1_msgs},
        "week2_texts": {m[2] for m in week2_msgs},
    }


@pytest.mark.asyncio(loop_scope="function")
async def test_week_chat_bounds_split(db_session, teacher_setup):
    session = teacher_setup["session"]
    lower1, upper1 = await _week_chat_bounds(db_session, session, 1)
    lower2, upper2 = await _week_chat_bounds(db_session, session, 2)

    assert lower1 is not None
    assert upper1 is not None
    assert lower2 == upper1
    assert upper2 is None


@pytest.mark.asyncio(loop_scope="function")
async def test_session_message_stats_per_week(db_session, teacher_setup):
    session = teacher_setup["session"]
    w1_rounds, _ = await _session_message_stats(db_session, session, 1)
    w2_rounds, _ = await _session_message_stats(db_session, session, 2)

    assert w1_rounds == 1
    assert w2_rounds == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_teacher_chat_messages_filtered_by_week(test_client, teacher_setup):
    classroom = teacher_setup["classroom"]
    student = teacher_setup["student"]
    headers = teacher_setup["teacher_headers"]

    r1 = await test_client.get(
        f"/teacher/classes/{classroom.id}/students/{student.id}/chat-messages?week=1",
        headers=headers,
    )
    assert r1.status_code == 200
    texts1 = {m["text"] for m in r1.json()}
    assert texts1 == teacher_setup["week1_texts"]

    r2 = await test_client.get(
        f"/teacher/classes/{classroom.id}/students/{student.id}/chat-messages?week=2",
        headers=headers,
    )
    assert r2.status_code == 200
    texts2 = {m["text"] for m in r2.json()}
    assert texts2 == teacher_setup["week2_texts"]


@pytest.mark.asyncio(loop_scope="function")
async def test_teacher_summary_interaction_count_matches_week(test_client, teacher_setup):
    classroom = teacher_setup["classroom"]
    student = teacher_setup["student"]
    headers = teacher_setup["teacher_headers"]

    r = await test_client.get(
        f"/teacher/classes/{classroom.id}/students/{student.id}/summary?week=2",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["interaction_count"] == 1
