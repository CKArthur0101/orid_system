"""Dry-run and one-transaction import for the formal experiment roster."""
from __future__ import annotations

import json
import logging
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from uuid import UUID, uuid4

from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ClassRoom,
    ExperimentImportBatch,
    StudentClassMembership,
    TeacherClassAssignment,
    User,
)
from app.services.experiment_cohort import (
    EXPERIMENT_CLASS_CODES,
    EXPERIMENT_TEACHERS,
    EXPERIMENT_YEAR,
    LEGACY_ARCHIVE_CODES,
    LEGACY_ARCHIVE_NAMES,
    RosterPlan,
    classify_roster_rows,
    cohort_password_errors,
    study_condition_for_code,
    teacher_login,
)

logger = logging.getLogger(__name__)
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_password_helper = PasswordHelper()


def parse_roster_xlsx(payload: bytes) -> list[tuple[str, str, str, str]]:
    with zipfile.ZipFile(BytesIO(payload)) as workbook:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", _NS):
                texts = [
                    node.text or ""
                    for node in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                ]
                shared.append("".join(texts))
        sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
    rows: list[tuple[str, str, str, str]] = []
    for row in sheet.findall("m:sheetData/m:row", _NS):
        values: list[str] = []
        for cell in row.findall("m:c", _NS):
            ref = cell.attrib.get("r", "")
            column = "".join(ch for ch in ref if ch.isalpha())
            kind = cell.attrib.get("t")
            node = cell.find("m:v", _NS)
            text = ""
            if node is not None and node.text is not None:
                text = shared[int(node.text)] if kind == "s" else node.text
            index = 0
            for ch in column:
                index = index * 26 + ord(ch) - 64
            while len(values) < index:
                values.append("")
            if index:
                values[index - 1] = text
        while len(values) < 4:
            values.append("")
        if any(str(item).strip() for item in values[:4]):
            rows.append((values[0], values[1], values[2], values[3]))
    return rows


async def _class_by_code(db: AsyncSession) -> dict[str, ClassRoom]:
    result = await db.execute(
        select(ClassRoom).where(
            ClassRoom.year == EXPERIMENT_YEAR,
            ClassRoom.external_code.in_(EXPERIMENT_CLASS_CODES),
        )
    )
    return {str(row.external_code): row for row in result.scalars().all() if row.external_code}


async def build_roster_plan(db: AsyncSession, rows: list[tuple[str, str, str, str]]) -> RosterPlan:
    classes = await _class_by_code(db)
    class_id_to_code = {row.id: code for code, row in classes.items()}
    memberships = await db.execute(
        select(User.email, User.display_name, StudentClassMembership.class_id, StudentClassMembership.seat_no)
        .join(StudentClassMembership, StudentClassMembership.student_id == User.id)
        .where(StudentClassMembership.class_id.in_(list(class_id_to_code)))
    ) if class_id_to_code else None
    existing_students: dict[str, tuple[str, str, int | None]] = {}
    if memberships is not None:
        for email, display_name, class_id, seat_no in memberships.all():
            code = class_id_to_code.get(class_id)
            if code:
                existing_students[str(email)] = (str(display_name or ""), code, seat_no)

    assignments = await db.execute(
        select(User.email, User.display_name, TeacherClassAssignment.class_id)
        .join(TeacherClassAssignment, TeacherClassAssignment.teacher_id == User.id)
        .where(TeacherClassAssignment.class_id.in_(list(class_id_to_code)))
    ) if class_id_to_code else None
    existing_teachers: dict[str, tuple[str, str]] = {}
    if assignments is not None:
        for email, display_name, class_id in assignments.all():
            code = class_id_to_code.get(class_id)
            if code:
                existing_teachers[str(email)] = (str(display_name or ""), code)

    # A login that already exists outside these classes is still a conflict.
    wanted = [item["login"] for item in classify_roster_rows(rows).student_rows]
    wanted.extend(login for _, _, login in EXPERIMENT_TEACHERS)
    if wanted:
        found = await db.execute(select(User.email, User.display_name, User.role).where(User.email.in_(wanted)))
        for email, display_name, role in found.all():
            login = str(email)
            if login not in existing_students and login not in existing_teachers:
                if str(role) == "teacher" and login.endswith("teacher"):
                    existing_teachers[login] = (str(display_name or ""), "")
                else:
                    existing_students[login] = (str(display_name or ""), "", None)
    return classify_roster_rows(
        rows,
        existing_students=existing_students,
        existing_teachers=existing_teachers,
    )


async def user_is_experiment_cohort(db: AsyncSession, user: User) -> bool:
    student = await db.execute(
        select(ClassRoom.external_code)
        .join(StudentClassMembership, StudentClassMembership.class_id == ClassRoom.id)
        .where(StudentClassMembership.student_id == user.id)
    )
    teacher = await db.execute(
        select(ClassRoom.external_code)
        .join(TeacherClassAssignment, TeacherClassAssignment.class_id == ClassRoom.id)
        .where(TeacherClassAssignment.teacher_id == user.id)
    )
    codes = {str(code) for code in student.scalars().all() if code}
    codes.update(str(code) for code in teacher.scalars().all() if code)
    return bool(codes & set(EXPERIMENT_CLASS_CODES))


def _hash_initial_password(login: str) -> str:
    errors = cohort_password_errors(login)
    if errors:
        raise ValueError("initial password rejected")
    return _password_helper.hash(login)


async def _ensure_classes(db: AsyncSession) -> dict[str, ClassRoom]:
    classes = await _class_by_code(db)
    for code in EXPERIMENT_CLASS_CODES:
        if code in classes:
            row = classes[code]
            if row.study_condition != study_condition_for_code(code):
                row.study_condition = study_condition_for_code(code)
            continue
        row = ClassRoom(
            id=uuid4(),
            name=code,
            year=EXPERIMENT_YEAR,
            external_code=code,
            study_condition=study_condition_for_code(code),
        )
        db.add(row)
        classes[code] = row
    await db.flush()
    return classes


async def commit_roster_import(
    db: AsyncSession,
    rows: list[tuple[str, str, str, str]],
    *,
    created_by: UUID,
) -> tuple[RosterPlan, list[str]]:
    plan = await build_roster_plan(db, rows)
    if not plan.ok:
        logger.info(
            "experiment import refused",
            extra={
                "conflicts": len(plan.conflicts),
                "errors": len(plan.errors),
                "students_to_create": plan.students_to_create,
                "teachers_to_create": plan.teachers_to_create,
            },
        )
        return plan, []

    classes = await _ensure_classes(db)
    created: list[str] = []
    for code, teacher_name, login in EXPERIMENT_TEACHERS:
        existing = await db.execute(select(User).where(User.email == login))
        user = existing.scalars().first()
        if user is None:
            user = User(
                id=uuid4(),
                email=login,
                hashed_password=_hash_initial_password(login),
                is_active=True,
                is_superuser=False,
                is_verified=True,
                role="teacher",
                display_name=teacher_name,
                orid_condition="experimental",
            )
            db.add(user)
            await db.flush()
            created.append(login)
        classroom = classes[code]
        link = await db.execute(
            select(TeacherClassAssignment).where(
                TeacherClassAssignment.teacher_id == user.id,
                TeacherClassAssignment.class_id == classroom.id,
            )
        )
        if link.scalars().first() is None:
            db.add(TeacherClassAssignment(id=uuid4(), teacher_id=user.id, class_id=classroom.id))

    for item in plan.student_rows:
        login = item["login"]
        existing = await db.execute(select(User).where(User.email == login))
        if existing.scalars().first() is not None:
            continue
        user = User(
            id=uuid4(),
            email=login,
            hashed_password=_hash_initial_password(login),
            is_active=True,
            is_superuser=False,
            is_verified=True,
            role="student",
            display_name=item["display_name"],
            orid_condition=item["orid_condition"],
        )
        db.add(user)
        await db.flush()
        classroom = classes[item["class_code"]]
        db.add(
            StudentClassMembership(
                id=uuid4(),
                student_id=user.id,
                class_id=classroom.id,
                seat_no=item["seat_no"],
            )
        )
        created.append(login)

    batch = ExperimentImportBatch(
        id=uuid4(),
        created_by=created_by,
        status="committed",
        created_login_ids=json.dumps(created, ensure_ascii=False),
    )
    db.add(batch)
    logger.info(
        "experiment import committed",
        extra={"created": len(created), "skipped_507": plan.skipped_507},
    )
    return plan, created


async def archive_legacy_classes(db: AsyncSession) -> list[str]:
    from datetime import datetime, timezone

    result = await db.execute(select(ClassRoom))
    archived: list[str] = []
    now = datetime.now(timezone.utc)
    for row in result.scalars().all():
        code = str(row.external_code or "")
        if row.name in LEGACY_ARCHIVE_NAMES or code in LEGACY_ARCHIVE_CODES:
            if row.archived_at is None:
                row.archived_at = now
                archived.append(row.name)
    return archived


def teacher_logins() -> list[str]:
    return [teacher_login(code) for code, _, _ in EXPERIMENT_TEACHERS]
