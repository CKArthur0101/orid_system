"""
建立本機／研究用測試帳號（學生 + 教師）。

執行方式（在 fastapi_backend 目錄、且已設定 DATABASE_URL，並已 alembic upgrade）：

  uv run python commands/seed_test_accounts.py

Docker backend 容器內：

  python commands/seed_test_accounts.py

若已存在相同登入帳號（user.email），會更新密碼、role、display_name（方便重設測試密碼）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

_backend_root = Path(__file__).resolve().parents[1]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from dotenv import load_dotenv
from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.database import async_session_maker
from app.models import ClassRoom, StudentClassMembership, TeacherClassAssignment, User

load_dotenv()

DEFAULT_STUDENT_LOGIN = "114524021"
DEFAULT_STUDENT_DISPLAY_NAME = "林宜萱"
# 與 migration「學號登入」示範帳一致（若已由 migration 改名，seed 會重設密碼方便本機測試）
KY_STUDENT_LOGIN = "114524020"
KY_STUDENT_DISPLAY_NAME = "邱振凱"
DEFAULT_TEACHER_LOGIN = "orid.teacher@example.com"
DEFAULT_TEACHER_DISPLAY_NAME = "示範教師"
# 符合 UserManager.validate_password：長度、大寫、特殊字元；不可與登入帳號完全相同
DEFAULT_PASSWORD = "OridTest2026!"

CLASS_NAME = "ORID 測試班"


async def _ensure_user(
    *,
    email: str,
    password: str,
    role: str,
    display_name: str | None = None,
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
            if display_name is not None:
                u.display_name = display_name
            await db.commit()
            await db.refresh(u)
            print(f"[update] {email} role={role} display_name={u.display_name!r}")
            return u

        nu = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=ph.hash(password),
            is_active=True,
            is_superuser=False,
            is_verified=True,
            role=role,
            display_name=display_name,
        )
        db.add(nu)
        await db.commit()
        await db.refresh(nu)
        print(f"[create] {email} role={role} display_name={display_name!r}")
        return nu


async def _ensure_demo_class_links(students: list[User], teacher: User) -> None:
    """建立示範班級並綁定教師／學生（需已執行 teacher RBAC migration）。"""
    async with async_session_maker() as db:
        r = await db.execute(select(ClassRoom).where(ClassRoom.name == CLASS_NAME).limit(1))
        cls = r.scalars().first()
        if not cls:
            cls = ClassRoom(name=CLASS_NAME, year=2026, external_code="demo")
            db.add(cls)
            await db.flush()

        for st in students:
            m1 = await db.execute(
                select(StudentClassMembership).where(
                    StudentClassMembership.student_id == st.id,
                    StudentClassMembership.class_id == cls.id,
                )
            )
            if not m1.scalars().first():
                db.add(StudentClassMembership(student_id=st.id, class_id=cls.id))

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
    student_login: str,
    student_display_name: str,
    teacher_login: str,
    teacher_display_name: str,
    password: str,
    with_class: bool,
) -> None:
    student = await _ensure_user(
        email=student_login,
        password=password,
        role="student",
        display_name=student_display_name,
    )
    teacher = await _ensure_user(
        email=teacher_login,
        password=password,
        role="teacher",
        display_name=teacher_display_name,
    )
    ky_student = await _ensure_user(
        email=KY_STUDENT_LOGIN,
        password=password,
        role="student",
        display_name=KY_STUDENT_DISPLAY_NAME,
    )

    if with_class:
        try:
            await _ensure_demo_class_links([student, ky_student], teacher)
        except ProgrammingError as e:
            print(
                "[warn] 無法建立班級關聯（可能尚未執行 teacher RBAC migration）。"
                f" 詳情：{e}"
            )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed ORID test student/teacher accounts.")
    p.add_argument(
        "--student-login",
        default=DEFAULT_STUDENT_LOGIN,
        help="Student login id (stored in user.email)",
    )
    p.add_argument(
        "--student-display-name",
        default=DEFAULT_STUDENT_DISPLAY_NAME,
    )
    p.add_argument(
        "--teacher-login",
        default=DEFAULT_TEACHER_LOGIN,
        help="Teacher login id (often still an email)",
    )
    p.add_argument(
        "--teacher-display-name",
        default=DEFAULT_TEACHER_DISPLAY_NAME,
    )
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
            student_login=args.student_login,
            student_display_name=args.student_display_name,
            teacher_login=args.teacher_login,
            teacher_display_name=args.teacher_display_name,
            password=args.password,
            with_class=args.with_class,
        )
    )
