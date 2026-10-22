"""Formal 115 experiment classes, logins, and the password rule for that cohort only."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

EXPERIMENT_YEAR = 2026
EXPERIMENT_CLASS_CODES = ("501", "502", "503", "504", "505", "506", "508", "509")
EXPERIMENTAL_CODES = frozenset({"501", "504", "505", "508"})
CONTROL_CODES = frozenset({"502", "503", "506", "509"})
LEGACY_ARCHIVE_NAMES = frozenset({"南勢國小", "蚵間國小"})
LEGACY_ARCHIVE_CODES = frozenset({"Nanshih", "kejian-guo-xiao"})

EXPERIMENT_TEACHERS: tuple[tuple[str, str, str], ...] = (
    ("501", "鄒欣潔", "501teacher"),
    ("502", "李姿穎", "502teacher"),
    ("503", "周雯玲", "503teacher"),
    ("504", "黃蘭麗", "504teacher"),
    ("505", "劉欣怡", "505teacher"),
    ("506", "鍾亦亭", "506teacher"),
    ("508", "蔡耀興", "508teacher"),
    ("509", "羅仕昇", "509teacher"),
)


def study_condition_for_code(code: str) -> str:
    if code in EXPERIMENTAL_CODES:
        return "experimental"
    if code in CONTROL_CODES:
        return "control"
    raise ValueError(f"unknown experiment class {code}")


def student_login(class_code: str, seat_no: int) -> str:
    return f"{class_code}{int(seat_no):02d}"


def teacher_login(class_code: str) -> str:
    return f"{class_code}teacher"


def cohort_password_errors(password: str) -> list[str]:
    """Blank is rejected. Digits, letters, or both are allowed, including matching the login."""
    if password is None or not str(password):
        return ["Password is required."]
    if len(password) > 128:
        return ["Password is too long."]
    if not re.fullmatch(r"[A-Za-z0-9]+", password):
        return ["Password should contain only letters and numbers."]
    return []


def strict_password_errors(password: str) -> list[str]:
    errors: list[str] = []
    if password is None or len(password) < 6:
        errors.append("Password should be at least 6 characters.")
    if not password or not re.search(r"[A-Za-z]", password):
        errors.append("Password should contain at least one letter.")
    if not password or not re.search(r"[0-9]", password):
        errors.append("Password should contain at least one number.")
    if not password or not re.fullmatch(r"[A-Za-z0-9]+", password):
        errors.append("Password should contain only letters and numbers.")
    return errors


@dataclass
class RosterIssue:
    login: str
    reason: str


@dataclass
class RosterPlan:
    students_to_create: int = 0
    teachers_to_create: int = 0
    skipped_507: int = 0
    skipped_existing: int = 0
    conflicts: list[RosterIssue] = field(default_factory=list)
    errors: list[RosterIssue] = field(default_factory=list)
    student_rows: list[dict] = field(default_factory=list)
    class_student_counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.conflicts and not self.errors


def class_code_from_roster_number(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text.isdigit():
        return None
    number = int(text)
    if number == 7:
        return None
    if number < 1 or number > 9:
        return None
    return f"{500 + number}"


def classify_roster_rows(
    rows: list[tuple[str, str, str, str]],
    *,
    existing_students: dict[str, tuple[str, str, int | None]] | None = None,
    existing_teachers: dict[str, tuple[str, str]] | None = None,
) -> RosterPlan:
    """Classify roster rows without writing.

    existing_students maps login -> (display_name, class_code, seat_no).
    existing_teachers maps login -> (display_name, class_code).
    """
    plan = RosterPlan(class_student_counts={code: 0 for code in EXPERIMENT_CLASS_CODES})
    existing_students = existing_students or {}
    existing_teachers = existing_teachers or {}
    seen_logins: set[str] = set()
    seen_seats: set[tuple[str, int]] = set()

    for name, grade, class_no, seat in rows:
        display = str(name or "").strip()
        grade_text = str(grade or "").strip()
        class_text = str(class_no or "").strip()
        seat_text = str(seat or "").strip()
        if class_text == "7":
            plan.skipped_507 += 1
            continue
        code = class_code_from_roster_number(class_text)
        if grade_text != "5" or code is None or not seat_text.isdigit():
            plan.errors.append(RosterIssue(login="", reason="invalid_row"))
            continue
        seat_no = int(seat_text)
        if seat_no < 1 or seat_no > 99 or not display:
            plan.errors.append(RosterIssue(login="", reason="invalid_row"))
            continue
        login = student_login(code, seat_no)
        if login in seen_logins or (code, seat_no) in seen_seats:
            plan.errors.append(RosterIssue(login=login, reason="duplicate_in_file"))
            continue
        seen_logins.add(login)
        seen_seats.add((code, seat_no))
        plan.class_student_counts[code] = plan.class_student_counts.get(code, 0) + 1
        current = existing_students.get(login)
        if current is not None:
            current_name, current_code, current_seat = current
            if current_name == display and current_code == code and current_seat == seat_no:
                plan.skipped_existing += 1
                continue
            plan.conflicts.append(RosterIssue(login=login, reason="account_mismatch"))
            continue
        plan.students_to_create += 1
        plan.student_rows.append(
            {
                "login": login,
                "display_name": display,
                "class_code": code,
                "seat_no": seat_no,
                "orid_condition": study_condition_for_code(code),
            }
        )

    for code, teacher_name, login in EXPERIMENT_TEACHERS:
        current = existing_teachers.get(login)
        if current is not None:
            current_name, current_code = current
            if current_name == teacher_name and current_code == code:
                plan.skipped_existing += 1
                continue
            plan.conflicts.append(RosterIssue(login=login, reason="account_mismatch"))
            continue
        if login in existing_students:
            plan.conflicts.append(RosterIssue(login=login, reason="account_mismatch"))
            continue
        plan.teachers_to_create += 1
    return plan
