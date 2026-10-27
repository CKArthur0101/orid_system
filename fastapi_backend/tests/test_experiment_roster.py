"""Roster, cohort passwords, and login lock. These tests do not open a database."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import asyncio

import pytest
from fastapi import HTTPException
from fastapi_users.exceptions import InvalidPasswordException

from app.routes.admin import validate_admin_password
from app.routes.orid import _reject_student_flow_for_teacher
from app.routes.teacher import _get_allowed_class_ids
from app.schemas import UserCreate
from app.services.experiment_cohort import (
    CONTROL_CODES,
    EXPERIMENT_CLASS_CODES,
    EXPERIMENT_TEACHERS,
    EXPERIMENTAL_CODES,
    classify_roster_rows,
    cohort_password_errors,
    one_time_password_errors,
    teacher_student_password,
    strict_password_errors,
    study_condition_for_code,
    demo_accounts,
    student_login,
)
from app.services.experiment_import import _hash_initial_password
from app.services.login_lock import is_locked, record_failure, record_success
from app.users import UserManager


CLASS_COUNTS = {
    "1": 31,
    "2": 31,
    "3": 31,
    "4": 30,
    "5": 32,
    "6": 30,
    "7": 31,
    "8": 31,
    "9": 30,
}


def _roster() -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for class_no, count in CLASS_COUNTS.items():
        for seat in range(1, count + 1):
            rows.append((f"學生{class_no}-{seat}", "5", class_no, str(seat)))
    return rows


def test_roster_creates_246_students_skips_507_and_adds_8_teachers():
    plan = classify_roster_rows(_roster())
    assert plan.students_to_create == 246
    assert plan.teachers_to_create == 8
    assert plan.skipped_507 == 31
    assert plan.class_student_counts == {
        "501": 31,
        "502": 31,
        "503": 31,
        "504": 30,
        "505": 32,
        "506": 30,
        "508": 31,
        "509": 30,
    }
    assert sum(plan.class_student_counts.values()) == 246
    assert plan.ok
    logins = [row["login"] for row in plan.student_rows]
    logins.extend(login for _, _, login in EXPERIMENT_TEACHERS)
    assert len(logins) == 254
    assert len(set(logins)) == 254
    assert "507" not in EXPERIMENT_CLASS_CODES
    assert all(row["class_code"] != "507" for row in plan.student_rows)


def test_study_conditions_follow_class_codes():
    assert EXPERIMENTAL_CODES == {"501", "504", "505", "508"}
    assert CONTROL_CODES == {"502", "503", "506", "509"}
    by_code = {row["class_code"]: row["orid_condition"] for row in classify_roster_rows(_roster()).student_rows}
    assert by_code["501"] == "experimental"
    assert by_code["502"] == "control"
    assert study_condition_for_code("508") == "experimental"
    assert study_condition_for_code("509") == "control"


def test_existing_match_skips_and_mismatch_conflicts():
    login = student_login("501", 1)
    same = classify_roster_rows(
        [("學生1-1", "5", "1", "1")],
        existing_students={login: ("學生1-1", "501", 1)},
    )
    assert same.skipped_existing == 1
    assert same.students_to_create == 0
    clash = classify_roster_rows(
        [("另一人", "5", "1", "1")],
        existing_students={login: ("學生1-1", "501", 1)},
    )
    assert clash.conflicts[0].login == login
    assert not clash.ok


def test_cohort_passwords_allow_digits_and_login_match_only_for_this_batch():
    assert cohort_password_errors("50101") == []
    assert cohort_password_errors("501teacher") == []
    assert cohort_password_errors("")
    assert cohort_password_errors("50101!")
    assert strict_password_errors("50101")
    assert strict_password_errors("501teacher") == []
    validate_admin_password("50101", cohort=True)
    validate_admin_password("501teacher", cohort=True)
    with pytest.raises(HTTPException):
        validate_admin_password("50101", cohort=False)


def test_public_registration_still_rejects_password_equal_to_login():
    manager = UserManager(object())

    async def _check() -> None:
        await manager.validate_password(
            "501teacher",
            UserCreate(email="501teacher", password="501teacher"),
        )

    with pytest.raises(InvalidPasswordException):
        asyncio.run(_check())


def test_initial_password_is_hashed():
    hashed = _hash_initial_password("50101")
    assert hashed.startswith("$argon2")
    assert "50101" not in hashed


def test_login_lock_after_eight_failures_and_clears_on_success():
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    state = record_success()
    for _ in range(7):
        state = record_failure(state, now)
        assert not is_locked(state, now)
    state = record_failure(state, now)
    assert is_locked(state, now)
    assert not is_locked(state, now + timedelta(minutes=15))
    assert record_success().fail_count == 0


class _Rows:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _DB:
    def __init__(self, values):
        self.values = values

    async def execute(self, _statement):
        return _Rows(self.values)


def test_teacher_class_ids_come_only_from_assignments():
    own = uuid4()

    async def _check() -> None:
        teacher = SimpleNamespace(id=uuid4(), role="teacher")
        allowed = await _get_allowed_class_ids(_DB([own]), teacher)
        assert allowed == {own}
        admin = SimpleNamespace(id=uuid4(), role="admin")
        everything = await _get_allowed_class_ids(_DB([own, uuid4()]), admin)
        assert own in everything
        student = SimpleNamespace(id=uuid4(), role="student")
        with pytest.raises(HTTPException) as raised:
            await _get_allowed_class_ids(_DB([]), student)
        assert raised.value.status_code == 403

    asyncio.run(_check())


def test_demo_accounts_follow_each_class_and_stay_out_of_seat_logins():
    accounts = demo_accounts()
    assert [item["login"] for item in accounts] == [
        "501demo",
        "502demo",
        "503demo",
        "504demo",
        "505demo",
        "506demo",
        "508demo",
        "509demo",
    ]
    by_login = {item["login"]: item["orid_condition"] for item in accounts}
    assert by_login["501demo"] == "experimental"
    assert by_login["502demo"] == "control"
    assert by_login["509demo"] == "control"
    assert "507demo" not in by_login
    seat_logins = {student_login(code, seat) for code in EXPERIMENT_CLASS_CODES for seat in range(1, 40)}
    assert seat_logins.isdisjoint(by_login)


def test_one_time_password_accepts_any_non_blank_value():
    assert one_time_password_errors("1234") == []
    assert one_time_password_errors("柿子") == []
    assert one_time_password_errors("  ") == ["請輸入密碼。"]
    assert one_time_password_errors("x" * 129) == ["密碼太長。"]


def test_teacher_sees_login_until_student_sets_a_visible_password():
    unchanged = SimpleNamespace(email="50101", password_visible=None, password_change_used=False)
    changed = SimpleNamespace(email="50101", password_visible="柿子", password_change_used=True)
    assert teacher_student_password(unchanged) == "50101"
    assert teacher_student_password(changed) == "柿子"


def test_teacher_cannot_enter_student_writing_flow():
    with pytest.raises(HTTPException) as raised:
        _reject_student_flow_for_teacher(SimpleNamespace(role="teacher"))
    assert raised.value.status_code == 403
    _reject_student_flow_for_teacher(SimpleNamespace(role="student"))
    _reject_student_flow_for_teacher(SimpleNamespace(role="admin"))
