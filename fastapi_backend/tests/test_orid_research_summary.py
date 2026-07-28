"""Tests for the ORID Teacher Research MVP: OridWeeklyResearchSummary hooks
and the teacher research-overview aggregation endpoint."""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from app.models import (
    ClassRoom,
    OridSession,
    OridWeeklyResearchSummary,
    Reading,
    StudentClassMembership,
    TeacherClassAssignment,
    User,
)
from app.services.orid_research_summary import (
    compute_content_fingerprint,
    compute_word_count,
    normalize_writing_text,
    task_type_for_week,
)
from app.users import get_jwt_strategy


def _minimal_book_pack() -> str:
    return json.dumps(
        {
            "schema": "book_pack_v1",
            "version": 999,
            "book_title": "單元測試用書",
            "characters": [{"name": "阿松爺爺", "role": "故事角色"}],
            "key_events": ["測試事件一"],
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Pure unit tests — no DB
# ---------------------------------------------------------------------------
class TestNormalizeWritingText:
    def test_strips_all_whitespace(self):
        assert normalize_writing_text("阿松爺爺  很\n難過") == "阿松爺爺很難過"

    def test_none_becomes_empty(self):
        assert normalize_writing_text(None) == ""


class TestTaskTypeForWeek:
    def test_odd_week_is_orid_stage(self):
        assert task_type_for_week(1) == "orid_stage"
        assert task_type_for_week(3) == "orid_stage"

    def test_even_week_is_synthesis(self):
        assert task_type_for_week(2) == "synthesis"
        assert task_type_for_week(6) == "synthesis"


class TestComputeWordCount:
    def _obj(self, o="", r="", synthesis=None):
        obj = {
            "schema": "orid_writing_v1",
            "stages": {
                "O": {"d1": o},
                "R": {"d1": r},
                "I": {"d1": ""},
                "D": {"d1": ""},
            },
        }
        if synthesis is not None:
            obj["synthesis_draft"] = synthesis
        return obj

    def test_odd_week_sums_stage_d1_only(self):
        obj = self._obj(o="abc", r="de")
        assert compute_word_count(obj, week=1) == 5

    def test_odd_week_ignores_synthesis_draft(self):
        obj = self._obj(o="abc", synthesis="should not count on odd week")
        assert compute_word_count(obj, week=1) == 3

    def test_even_week_includes_synthesis_draft(self):
        obj = self._obj(o="abc", synthesis="xyz")
        assert compute_word_count(obj, week=2) == 6

    def test_whitespace_normalized_before_counting(self):
        obj = self._obj(o="a b\nc")
        assert compute_word_count(obj, week=1) == 3

    def test_none_writing_obj_is_zero(self):
        assert compute_word_count(None, week=1) == 0


class TestComputeContentFingerprint:
    def test_same_text_same_fingerprint(self):
        obj1 = {"schema": "orid_writing_v1", "stages": {"O": {"d1": "同一段文字"}}}
        obj2 = {"schema": "orid_writing_v1", "stages": {"O": {"d1": "同一段文字"}}}
        assert compute_content_fingerprint(obj1, week=1) == compute_content_fingerprint(obj2, week=1)

    def test_changed_text_changes_fingerprint(self):
        obj1 = {"schema": "orid_writing_v1", "stages": {"O": {"d1": "原始草稿"}}}
        obj2 = {"schema": "orid_writing_v1", "stages": {"O": {"d1": "修改後的草稿"}}}
        assert compute_content_fingerprint(obj1, week=1) != compute_content_fingerprint(obj2, week=1)

    def test_whitespace_only_change_is_not_a_revision(self):
        obj1 = {"schema": "orid_writing_v1", "stages": {"O": {"d1": "文字內容"}}}
        obj2 = {"schema": "orid_writing_v1", "stages": {"O": {"d1": " 文字 內容 "}}}
        assert compute_content_fingerprint(obj1, week=1) == compute_content_fingerprint(obj2, week=1)


# ---------------------------------------------------------------------------
# API tests — save_intent → is_submitted / save_count / revision_count
# ---------------------------------------------------------------------------
def _writing_v1(week: int, o_text: str) -> str:
    return json.dumps(
        {
            "schema": "orid_writing_v1",
            "week": week,
            "stages": {
                "O": {"d1": o_text},
                "R": {"d1": ""},
                "I": {"d1": ""},
                "D": {"d1": ""},
            },
        },
        ensure_ascii=False,
    )


async def _fetch_summary(db_session, *, user_id, week, session_id) -> OridWeeklyResearchSummary | None:
    res = await db_session.execute(
        select(OridWeeklyResearchSummary).where(
            OridWeeklyResearchSummary.user_id == user_id,
            OridWeeklyResearchSummary.week == week,
            OridWeeklyResearchSummary.session_id == session_id,
        )
    )
    return res.scalars().first()


@pytest.mark.asyncio(loop_scope="function")
async def test_draft_save_bumps_save_count_but_not_submitted(test_client, db_session, authenticated_user):
    user = authenticated_user["user"]
    reading = Reading(title="第1週 研究測試", content="{}")
    db_session.add(reading)
    await db_session.commit()
    await db_session.refresh(reading)

    session = OridSession(user_id=user.id, reading_id=reading.id, condition="experimental")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    r = await test_client.post(
        "/orid/writings",
        json={
            "reading_id": str(reading.id),
            "session_id": str(session.id),
            "week": 1,
            "content": _writing_v1(1, "第一次草稿"),
        },
        headers=authenticated_user["headers"],
    )
    assert r.status_code == 200, r.text

    summary = await _fetch_summary(db_session, user_id=user.id, week=1, session_id=session.id)
    assert summary is not None
    assert summary.save_count == 1
    assert summary.revision_count == 0
    assert summary.is_submitted is False
    assert summary.word_count == len("第一次草稿")
    assert summary.condition == "experimental"


@pytest.mark.asyncio(loop_scope="function")
async def test_submit_marks_submitted_and_changed_content_bumps_revision(
    test_client, db_session, authenticated_user
):
    user = authenticated_user["user"]
    reading = Reading(title="第1週 研究測試2", content="{}")
    db_session.add(reading)
    await db_session.commit()
    await db_session.refresh(reading)

    session = OridSession(user_id=user.id, reading_id=reading.id, condition="control")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    # First save (draft) — establishes the baseline fingerprint.
    r1 = await test_client.post(
        "/orid/writings",
        json={
            "reading_id": str(reading.id),
            "session_id": str(session.id),
            "week": 3,
            "content": _writing_v1(3, "草稿版本一"),
        },
        headers=authenticated_user["headers"],
    )
    assert r1.status_code == 200, r1.text

    # Second save with different content + explicit submit.
    r2 = await test_client.post(
        "/orid/writings",
        json={
            "reading_id": str(reading.id),
            "session_id": str(session.id),
            "week": 3,
            "content": _writing_v1(3, "草稿版本二，內容已修改"),
            "save_intent": "submit",
        },
        headers=authenticated_user["headers"],
    )
    assert r2.status_code == 200, r2.text

    summary = await _fetch_summary(db_session, user_id=user.id, week=3, session_id=session.id)
    assert summary is not None
    assert summary.save_count == 2
    assert summary.revision_count == 1
    assert summary.is_submitted is True

    # A third save with unchanged content should not add another revision.
    r3 = await test_client.post(
        "/orid/writings",
        json={
            "reading_id": str(reading.id),
            "session_id": str(session.id),
            "week": 3,
            "content": _writing_v1(3, "草稿版本二，內容已修改"),
        },
        headers=authenticated_user["headers"],
    )
    assert r3.status_code == 200, r3.text
    summary = await _fetch_summary(db_session, user_id=user.id, week=3, session_id=session.id)
    assert summary.save_count == 3
    assert summary.revision_count == 1


# ---------------------------------------------------------------------------
# API tests — guide_use_count (control prompt-usage / feedback_button)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio(loop_scope="function")
async def test_prompt_usage_bumps_guide_use_count(test_client, db_session, authenticated_user):
    user = authenticated_user["user"]
    reading = Reading(title="第1週 提示測試", content="{}")
    db_session.add(reading)
    await db_session.commit()
    await db_session.refresh(reading)

    session = OridSession(user_id=user.id, reading_id=reading.id, condition="control")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    r1 = await test_client.post(
        "/orid/prompt-usage",
        json={"session_id": str(session.id), "week": 1, "stage": "O", "word_count": 0, "prompt_view_count": 1},
        headers=authenticated_user["headers"],
    )
    assert r1.status_code == 200, r1.text

    summary = await _fetch_summary(db_session, user_id=user.id, week=1, session_id=session.id)
    assert summary is not None
    assert summary.guide_use_count == 1

    r2 = await test_client.post(
        "/orid/prompt-usage",
        json={"session_id": str(session.id), "week": 1, "stage": "O", "word_count": 5, "prompt_view_count": 2},
        headers=authenticated_user["headers"],
    )
    assert r2.status_code == 200, r2.text
    summary = await _fetch_summary(db_session, user_id=user.id, week=1, session_id=session.id)
    assert summary.guide_use_count == 3


@pytest.mark.asyncio(loop_scope="function")
async def test_feedback_button_bumps_guide_use_count(test_client, db_session, authenticated_user):
    user = authenticated_user["user"]
    reading = Reading(title="第1週 回饋測試", content=_minimal_book_pack())
    db_session.add(reading)
    await db_session.commit()
    await db_session.refresh(reading)

    session = OridSession(user_id=user.id, reading_id=reading.id, condition="control", current_stage="O")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    r = await test_client.post(
        "/orid/writing-coach/chat",
        json={
            "session_id": str(session.id),
            "student_text": "故事裡阿松爺爺把柿子藏起來。",
            "stage": "O",
            "draft": "d1",
            "source": "feedback_button",
            "week": 1,
            "save_feedback": False,
        },
        headers=authenticated_user["headers"],
    )
    assert r.status_code == 200, r.text

    summary = await _fetch_summary(db_session, user_id=user.id, week=1, session_id=session.id)
    assert summary is not None
    assert summary.guide_use_count == 1


# ---------------------------------------------------------------------------
# API test — GET /teacher/classes/{class_id}/research-overview aggregation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio(loop_scope="function")
async def test_research_overview_groups_by_condition(test_client, db_session):
    ph = PasswordHelper()
    teacher = User(
        id=uuid.uuid4(),
        email="research_teacher@test.local",
        hashed_password=ph.hash("TeacherPass1"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="teacher",
        display_name="研究教師",
    )
    exp_student = User(
        id=uuid.uuid4(),
        email="exp_student@test.local",
        hashed_password=ph.hash("StudentPass1"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="student",
        display_name="實驗組學生",
        orid_condition="experimental",
    )
    ctrl_student = User(
        id=uuid.uuid4(),
        email="ctrl_student@test.local",
        hashed_password=ph.hash("StudentPass1"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="student",
        display_name="控制組學生",
        orid_condition="control",
    )
    classroom = ClassRoom(name="研究班", year=2026, external_code="research-class")
    reading = Reading(title="第1週（暫定教材）", content="{}")
    db_session.add_all([teacher, exp_student, ctrl_student, classroom, reading])
    await db_session.flush()

    db_session.add_all(
        [
            TeacherClassAssignment(teacher_id=teacher.id, class_id=classroom.id),
            StudentClassMembership(student_id=exp_student.id, class_id=classroom.id),
            StudentClassMembership(student_id=ctrl_student.id, class_id=classroom.id),
        ]
    )
    exp_session = OridSession(user_id=exp_student.id, reading_id=reading.id, condition="experimental")
    ctrl_session = OridSession(user_id=ctrl_student.id, reading_id=reading.id, condition="control")
    db_session.add_all([exp_session, ctrl_session])
    await db_session.flush()

    db_session.add_all(
        [
            OridWeeklyResearchSummary(
                user_id=exp_student.id,
                session_id=exp_session.id,
                class_id=classroom.id,
                week=1,
                task_type="orid_stage",
                condition="experimental",
                word_count=100,
                save_count=3,
                revision_count=2,
                guide_use_count=4,
                badge_count=2,
                total_score=60,
                is_submitted=True,
            ),
            OridWeeklyResearchSummary(
                user_id=ctrl_student.id,
                session_id=ctrl_session.id,
                class_id=classroom.id,
                week=1,
                task_type="orid_stage",
                condition="control",
                word_count=40,
                save_count=1,
                revision_count=0,
                guide_use_count=1,
                badge_count=1,
                total_score=30,
                is_submitted=False,
            ),
        ]
    )
    await db_session.commit()

    token = await get_jwt_strategy().write_token(teacher)
    headers = {"Authorization": f"Bearer {token}"}

    r = await test_client.get(
        f"/teacher/classes/{classroom.id}/research-overview?week=1",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["summary_cards"]["total_students"] == 2
    assert data["summary_cards"]["experimental_count"] == 1
    assert data["summary_cards"]["control_count"] == 1
    assert data["summary_cards"]["submitted_count"] == 1

    by_condition = {row["condition"]: row for row in data["group_comparison"]}
    assert by_condition["experimental"]["avg_word_count"] == 100
    assert by_condition["experimental"]["submission_rate"] == 1.0
    assert by_condition["control"]["avg_word_count"] == 40
    assert by_condition["control"]["submission_rate"] == 0.0

    assert len(data["student_rows"]) == 2

    trend_week1 = [t for t in data["weekly_trends"] if t["week"] == 1]
    assert {t["condition"] for t in trend_week1} == {"experimental", "control"}

    # Research CSV export should include both students.
    csv_res = await test_client.get(
        f"/teacher/classes/{classroom.id}/research-export?week=1",
        headers=headers,
    )
    assert csv_res.status_code == 200
    assert "exp_student@test.local" in csv_res.text
    assert "ctrl_student@test.local" in csv_res.text
