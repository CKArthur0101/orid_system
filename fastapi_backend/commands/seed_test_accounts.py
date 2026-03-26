"""
建立本機／研究用測試帳號（學生 + 教師）。

執行方式（在 fastapi_backend 目錄、且已設定 DATABASE_URL，並已 alembic upgrade）：

  uv run python commands/seed_test_accounts.py

Docker backend 容器內：

  python commands/seed_test_accounts.py

若已存在相同 email，會更新密碼與 role（方便重設測試密碼）。
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from dotenv import load_dotenv
from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.database import async_session_maker
from app.models import ClassRoom, StudentClassMembership, TeacherClassAssignment, User

load_dotenv()

DEFAULT_STUDENT_EMAIL = "orid.student@example.com"
DEFAULT_TEACHER_EMAIL = "orid.teacher@example.com"
# 符合 UserManager.validate_password：長度、大寫、特殊字元；且不包含 email 子字串
DEFAULT_PASSWORD = "OridTest2026!"

CLASS_NAME = "ORID 測試班"


async def _ensure_user(
    *,
    email: str,
    password: str,
    role: str,
) -> User:
    ph = PasswordHelper()
    async with async_session_maker() as db:
        r = await db.execute(select(User).where(User.email == email))
        u = r.scalars().first()
        if u:
            u.hashed_password = ph.hash(password)
            u.role = role
            u.is_active = True
            u.is_verified = True
            await db.commit()
            await db.refresh(u)
            print(f"[update] {email} role={role}")
            return u

        nu = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=ph.hash(password),
            is_active=True,
            is_superuser=False,
            is_verified=True,
            role=role,
        )
        db.add(nu)
        await db.commit()
        await db.refresh(nu)
        print(f"[create] {email} role={role}")
        return nu


async def _ensure_demo_class_links(student: User, teacher: User) -> None:
    """建立示範班級並綁定教師／學生（需已執行 teacher RBAC migration）。"""
    async with async_session_maker() as db:
        r = await db.execute(select(ClassRoom).where(ClassRoom.name == CLASS_NAME).limit(1))
        cls = r.scalars().first()
        if not cls:
            cls = ClassRoom(name=CLASS_NAME, year=2026, external_code="demo")
            db.add(cls)
            await db.flush()

        # student membership
        m1 = await db.execute(
            select(StudentClassMembership).where(
                StudentClassMembership.student_id == student.id,
                StudentClassMembership.class_id == cls.id,
            )
        )
        if not m1.scalars().first():
            db.add(StudentClassMembership(student_id=student.id, class_id=cls.id))

        # teacher assignment
        m2 = await db.execute(
            select(TeacherClassAssignment).where(
                TeacherClassAssignment.teacher_id == teacher.id,
                TeacherClassAssignment.class_id == cls.id,
            )
        )
        if not m2.scalars().first():
            db.add(TeacherClassAssignment(teacher_id=teacher.id, class_id=cls.id))

        await db.commit()
        print(f"[class] {CLASS_NAME} id={cls.id!s}")


async def main(
    *,
    student_email: str,
    teacher_email: str,
    password: str,
    with_class: bool,
) -> None:
    student = await _ensure_user(email=student_email, password=password, role="student")
    teacher = await _ensure_user(email=teacher_email, password=password, role="teacher")

    if with_class:
        try:
            await _ensure_demo_class_links(student, teacher)
        except ProgrammingError as e:
            print(
                "[warn] 無法建立班級關聯（可能尚未執行 teacher RBAC migration）。"
                f" 詳情：{e}"
            )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed ORID test student/teacher accounts.")
    p.add_argument("--student-email", default=DEFAULT_STUDENT_EMAIL)
    p.add_argument("--teacher-email", default=DEFAULT_TEACHER_EMAIL)
    p.add_argument("--password", default=DEFAULT_PASSWORD)
    p.add_argument(
        "--with-class",
        action="store_true",
        help="Also create demo class + student/teacher links (needs RBAC tables).",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(
        main(
            student_email=args.student_email,
            teacher_email=args.teacher_email,
            password=args.password,
            with_class=args.with_class,
        )
    )
