"""
建立／更新 prod 管理側帳與蚵間教師帳：

  114524020  — role=admin（可看所有班級）密碼 Chiu0101
  kejian_teacher — role=teacher，綁定「蚵間國小」密碼與管理員相同（Chiu0101）

執行（prod backend 容器）：

  docker compose -p orid-prod -f docker-compose.prod.yml exec -T backend sh -c \\
    "export DATABASE_URL='postgresql+asyncpg://postgres:PASS@db:5432/orid_prod' && \\
     uv run python commands/seed_kejian_admin_teacher.py"
"""

from __future__ import annotations

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

from app.database import async_session_maker
from app.models import ClassRoom, TeacherClassAssignment, User

load_dotenv()

ADMIN_LOGIN = "114524020"
ADMIN_DISPLAY = "邱振凱"
ADMIN_PASSWORD = "Chiu0101"

TEACHER_LOGIN = "kejian_teacher"
TEACHER_DISPLAY = "蚵間教師"
TEACHER_PASSWORD = "teacher123"

KEJIAN_CLASS_EXTERNAL_CODE = "kejian-guo-xiao"


async def _ensure_user(
    *,
    email: str,
    password: str,
    role: str,
    display_name: str,
    is_superuser: bool = False,
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
            u.is_superuser = is_superuser
            u.display_name = display_name
            await db.commit()
            await db.refresh(u)
            print(f"[update] {email} role={role} display_name={display_name!r}")
            return u

        nu = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=ph.hash(password),
            is_active=True,
            is_superuser=is_superuser,
            is_verified=True,
            role=role,
            display_name=display_name,
        )
        db.add(nu)
        await db.commit()
        await db.refresh(nu)
        print(f"[create] {email} role={role} display_name={display_name!r}")
        return nu


async def _link_teacher_to_kejian_class(teacher: User) -> None:
    async with async_session_maker() as db:
        r = await db.execute(
            select(ClassRoom)
            .where(ClassRoom.external_code == KEJIAN_CLASS_EXTERNAL_CODE)
            .limit(1)
        )
        cls = r.scalars().first()
        if not cls:
            r2 = await db.execute(
                select(ClassRoom).where(ClassRoom.name == "蚵間國小").limit(1)
            )
            cls = r2.scalars().first()
        if not cls:
            print("[warn] 找不到「蚵間國小」班級，略過教師班級綁定")
            return

        r3 = await db.execute(
            select(TeacherClassAssignment).where(
                TeacherClassAssignment.teacher_id == teacher.id,
                TeacherClassAssignment.class_id == cls.id,
            )
        )
        if not r3.scalars().first():
            db.add(TeacherClassAssignment(teacher_id=teacher.id, class_id=cls.id))

        await db.commit()
        print(f"[class] {TEACHER_LOGIN} -> {cls.name!r} id={cls.id}")


async def main() -> None:
    await _ensure_user(
        email=ADMIN_LOGIN,
        password=ADMIN_PASSWORD,
        role="admin",
        display_name=ADMIN_DISPLAY,
        is_superuser=True,
    )
    teacher = await _ensure_user(
        email=TEACHER_LOGIN,
        password=TEACHER_PASSWORD,
        role="teacher",
        display_name=TEACHER_DISPLAY,
    )
    await _link_teacher_to_kejian_class(teacher)


if __name__ == "__main__":
    asyncio.run(main())
