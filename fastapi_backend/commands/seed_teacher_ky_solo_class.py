"""
建立「僅能看 114524020」的教師帳與專班：

  班級：邱振凱專班（僅 114524020 一位學員）
  教師：teacher_ky / 顯示名稱「邱振凱指導教師」/ 密碼 teacher123

執行（prod）：

  docker compose -p orid-prod -f docker-compose.prod.yml exec -T backend sh -c \\
    "export DATABASE_URL='postgresql+asyncpg://postgres:PASS@db:5432/orid_prod' && \\
     uv run python commands/seed_teacher_ky_solo_class.py"
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
from app.models import ClassRoom, StudentClassMembership, TeacherClassAssignment, User

load_dotenv()

STUDENT_LOGIN = "114524020"
CLASS_NAME = "邱振凱專班"
CLASS_EXTERNAL_CODE = "ky-solo-114524020"

TEACHER_LOGIN = "teacher_ky"
TEACHER_DISPLAY = "邱振凱指導教師"
TEACHER_PASSWORD = "teacher123"


async def main() -> None:
    ph = PasswordHelper()
    async with async_session_maker() as db:
        r = await db.execute(select(User).where(User.email == STUDENT_LOGIN))
        student = r.scalars().first()
        if not student:
            print(f"[error] 找不到學員帳號 {STUDENT_LOGIN}")
            return

        r = await db.execute(
            select(ClassRoom)
            .where(ClassRoom.external_code == CLASS_EXTERNAL_CODE)
            .limit(1)
        )
        cls = r.scalars().first()
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

        all_m = await db.execute(
            select(StudentClassMembership).where(StudentClassMembership.class_id == cls.id)
        )
        for m in all_m.scalars().all():
            if m.student_id != student.id:
                await db.delete(m)

        r2 = await db.execute(
            select(StudentClassMembership).where(
                StudentClassMembership.class_id == cls.id,
                StudentClassMembership.student_id == student.id,
            )
        )
        if not r2.scalars().first():
            db.add(StudentClassMembership(student_id=student.id, class_id=cls.id))
        print(f"[class] student {STUDENT_LOGIN} -> {cls.name!r}")

        r = await db.execute(select(User).where(User.email == TEACHER_LOGIN))
        teacher = r.scalars().first()
        if teacher:
            teacher.hashed_password = ph.hash(TEACHER_PASSWORD)
            teacher.role = "teacher"
            teacher.is_active = True
            teacher.is_verified = True
            teacher.is_superuser = False
            teacher.display_name = TEACHER_DISPLAY
            print(f"[update] {TEACHER_LOGIN}")
        else:
            teacher = User(
                id=uuid.uuid4(),
                email=TEACHER_LOGIN,
                hashed_password=ph.hash(TEACHER_PASSWORD),
                is_active=True,
                is_superuser=False,
                is_verified=True,
                role="teacher",
                display_name=TEACHER_DISPLAY,
            )
            db.add(teacher)
            await db.flush()
            print(f"[create] {TEACHER_LOGIN}")

        old_assign = await db.execute(
            select(TeacherClassAssignment).where(
                TeacherClassAssignment.teacher_id == teacher.id
            )
        )
        for a in old_assign.scalars().all():
            if a.class_id != cls.id:
                await db.delete(a)

        r3 = await db.execute(
            select(TeacherClassAssignment).where(
                TeacherClassAssignment.teacher_id == teacher.id,
                TeacherClassAssignment.class_id == cls.id,
            )
        )
        if not r3.scalars().first():
            db.add(TeacherClassAssignment(teacher_id=teacher.id, class_id=cls.id))

        await db.commit()
        print(f"[done] teacher {TEACHER_LOGIN} 僅可看 {cls.name!r}（學員 {STUDENT_LOGIN}）")


if __name__ == "__main__":
    asyncio.run(main())
