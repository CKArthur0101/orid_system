"""
建立學生 Jimgo 並加入 DILAB 班級。

  登入帳號（email）: Jimgo
  密碼: Jimgo
  display_name: Jimgo
  role: student

執行（prod）：

  docker compose -p orid-prod -f docker-compose.prod.yml exec -T backend sh -c \\
    "export DATABASE_URL='postgresql+asyncpg://postgres:PASS@db:5432/orid_prod' && \\
     uv run python commands/seed_jimgo_dilab.py"
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
from app.models import ClassRoom, StudentClassMembership, User

load_dotenv()

LOGIN = "Jimgo"
PASSWORD = "Jimgo"
DISPLAY_NAME = "Jimgo"
CLASS_NAME = "DILAB"
CLASS_EXTERNAL_CODE = "dilab"


async def main() -> None:
    ph = PasswordHelper()
    async with async_session_maker() as db:
        r = await db.execute(
            select(ClassRoom).where(ClassRoom.external_code == CLASS_EXTERNAL_CODE).limit(1)
        )
        cls = r.scalars().first()
        if not cls:
            r2 = await db.execute(select(ClassRoom).where(ClassRoom.name == CLASS_NAME).limit(1))
            cls = r2.scalars().first()
        if not cls:
            cls = ClassRoom(
                id=uuid.uuid4(),
                name=CLASS_NAME,
                year=2026,
                external_code=CLASS_EXTERNAL_CODE,
            )
            db.add(cls)
            await db.flush()
            print(f"[create] class {CLASS_NAME!r}")
        elif not (cls.external_code or "").strip():
            cls.external_code = CLASS_EXTERNAL_CODE
            await db.flush()

        r = await db.execute(select(User).where(User.email == LOGIN))
        u = r.scalars().first()
        if u:
            u.hashed_password = ph.hash(PASSWORD)
            u.role = "student"
            u.is_active = True
            u.is_verified = True
            u.is_superuser = False
            u.display_name = DISPLAY_NAME
            print(f"[update] {LOGIN}")
        else:
            u = User(
                id=uuid.uuid4(),
                email=LOGIN,
                hashed_password=ph.hash(PASSWORD),
                is_active=True,
                is_superuser=False,
                is_verified=True,
                role="student",
                display_name=DISPLAY_NAME,
            )
            db.add(u)
            await db.flush()
            print(f"[create] {LOGIN}")

        r3 = await db.execute(
            select(StudentClassMembership).where(
                StudentClassMembership.student_id == u.id,
                StudentClassMembership.class_id == cls.id,
            )
        )
        if not r3.scalars().first():
            db.add(StudentClassMembership(student_id=u.id, class_id=cls.id))

        await db.commit()
        print(f"[done] {LOGIN} -> {cls.name!r} (student)")


if __name__ == "__main__":
    asyncio.run(main())
