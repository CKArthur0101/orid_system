"""
建立 10 組試測帳號：teacher1..teacher10、student1..student10，密碼預設 @Test123；
將 student1..10 與全部 teacher1..10 綁定到同一班級「測驗班級」（external_code 固定，避免同名誤綁）。

正式環境請在本機或後端容器內設定 DATABASE_URL 後執行，例如：

  cd fastapi_backend
  set DATABASE_URL=postgresql+asyncpg://...
  python commands/seed_pilot_accounts.py --env-file ..\\.env.prod --yes

若使用 uv：

  uv run python commands/seed_pilot_accounts.py --yes

本機虛擬環境（做法 A，建議 Python 3.11+）：

  py -3.11 -m venv .venv
  .\\.venv\\Scripts\\Activate.ps1
  python -m pip install -U pip wheel
  python -m pip install "python-dotenv>=1.0.1,<2" "pydantic-settings>=2.5.2,<3" "sqlalchemy>=2.0,<3" \\
    "asyncpg>=0.29.0,<0.30" "fastapi-users[sqlalchemy]>=13.0.0,<14" "fastapi[standard]>=0.115.0,<0.116" \\
    "fastapi-mail>=1.4.1,<2" "fastapi-pagination==0.13.3" "openai>=2.15.0" "faiss-cpu>=1.13.2" "numpy>=2.0" "alembic>=1.14.0,<2"

（`pip install -r requirements.txt` 若因 hash 與 faiss-cpu wheel 不符而失敗，可用上列與 pyproject 對齊的套件。）

（--yes 略過互動確認；未加 --yes 時會要求輸入 yes 才寫入資料庫。）
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

# 必須先載入 .env／--env-file，再 import app（Settings 會讀環境變數）
_early = argparse.ArgumentParser(add_help=False)
_early.add_argument("--env-file", default=None)
_early_args, _ = _early.parse_known_args()
if _early_args.env_file:
    load_dotenv(_early_args.env_file, override=True)
else:
    load_dotenv()

from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.database import async_session_maker
from app.models import ClassRoom, StudentClassMembership, TeacherClassAssignment, User

PILOT_PASSWORD = "@Test123"
PILOT_CLASS_NAME = "測驗班級"
# 僅用於程式辨識此試測班，避免與其他同名班級混淆
PILOT_CLASS_EXTERNAL_CODE = "pilot_quiz_class_2026"
PILOT_COUNT = 10


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


async def _ensure_pilot_class(students: list[User], teachers: list[User]) -> None:
    async with async_session_maker() as db:
        r = await db.execute(
            select(ClassRoom)
            .where(ClassRoom.external_code == PILOT_CLASS_EXTERNAL_CODE)
            .limit(1)
        )
        cls = r.scalars().first()
        if not cls:
            r2 = await db.execute(
                select(ClassRoom)
                .where(ClassRoom.name == PILOT_CLASS_NAME)
                .order_by(ClassRoom.created_at.asc())
                .limit(1)
            )
            cls = r2.scalars().first()
            if cls is not None and not (cls.external_code or "").strip():
                cls.external_code = PILOT_CLASS_EXTERNAL_CODE
                await db.flush()

        if not cls:
            cls = ClassRoom(
                name=PILOT_CLASS_NAME,
                year=2026,
                external_code=PILOT_CLASS_EXTERNAL_CODE,
            )
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

        for te in teachers:
            m2 = await db.execute(
                select(TeacherClassAssignment).where(
                    TeacherClassAssignment.teacher_id == te.id,
                    TeacherClassAssignment.class_id == cls.id,
                )
            )
            if not m2.scalars().first():
                db.add(TeacherClassAssignment(teacher_id=te.id, class_id=cls.id))

        await db.commit()
        print(f"[class] {PILOT_CLASS_NAME} id={cls.id!s} external_code={PILOT_CLASS_EXTERNAL_CODE!r}")


async def main(*, password: str, skip_confirm: bool) -> None:
    if not skip_confirm:
        print(
            "即將寫入資料庫：10 教師、10 學生、班級「測驗班級」與綁定。"
            " 若 DATABASE_URL 指向正式站，請確認無誤。"
        )
        ans = input("輸入 yes 繼續: ").strip().lower()
        if ans != "yes":
            print("已取消。")
            return

    teachers: list[User] = []
    students: list[User] = []
    for i in range(1, PILOT_COUNT + 1):
        teachers.append(
            await _ensure_user(
                email=f"teacher{i}",
                password=password,
                role="teacher",
                display_name=f"試測教師{i}",
            )
        )
        students.append(
            await _ensure_user(
                email=f"student{i}",
                password=password,
                role="student",
                display_name=f"試測學生{i}",
            )
        )

    try:
        await _ensure_pilot_class(students, teachers)
    except ProgrammingError as e:
        print(
            "[warn] 無法建立班級／綁定（可能尚未執行 teacher RBAC migration）。"
            f" 詳情：{e}"
        )
        raise

    print("[done] 帳號 teacher1..teacher10、student1..student10；密碼已設為（略）；班級已綁定。")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed 10 pilot teacher/student accounts + 測驗班級.")
    p.add_argument("--password", default=PILOT_PASSWORD, help="Password for all 20 accounts")
    p.add_argument(
        "--env-file",
        default=None,
        help="Optional path to .env (e.g. .env.prod); loaded with override=True",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    # 與模組頂端 early bootstrap 一致；若僅改密碼重跑可再載入一次
    if args.env_file:
        load_dotenv(args.env_file, override=True)
    else:
        load_dotenv()

    asyncio.run(main(password=args.password, skip_confirm=args.yes))
