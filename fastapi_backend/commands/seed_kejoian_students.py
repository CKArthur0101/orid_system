"""
在 orid_prod（或目前 DATABASE_URL 指向的庫）建立／更新 10 位學生帳號：
  登入帳號（user.email）: kejian01 … kejian10
  display_name: 蚵間老師一 … 蚵間老師十
  role: student
  預設密碼: test01

若先前為 kejoian-student-XX@seed.local，會改為 kejianXX 並保留 display_name。

執行（prod compose backend 容器內；`exec` 預設沒有 start.prod.sh 組出的 DATABASE_URL，請先 export）：

  docker compose -p orid-prod -f docker-compose.prod.yml exec -T backend sh -c \\
    "export DATABASE_URL='postgresql+asyncpg://USER:PASS@db:5432/orid_prod' && uv run python commands/seed_kejoian_students.py"
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
from app.models import User

load_dotenv()

DEFAULT_PASSWORD = "test01"
DISPLAY_ZH = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十")
LEGACY_EMAIL_TEMPLATE = "kejoian-student-{num:02d}@seed.local"


def _login_id(i: int) -> str:
    return f"kejian{i:02d}"


def _legacy_email(i: int) -> str:
    return LEGACY_EMAIL_TEMPLATE.format(num=i)


async def _ensure_user(
    *,
    email: str,
    password: str,
    role: str,
    display_name: str | None = None,
) -> None:
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
            print(f"[update] {email} role={role} display_name={display_name!r}")
            return

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
        print(f"[create] {email} role={role} display_name={display_name!r}")


async def _migrate_legacy_to_login(i: int, login: str, display: str, password: str) -> None:
    """將舊 seed 帳號 email 改為 kejianXX，並更新密碼。"""
    legacy = _legacy_email(i)
    ph = PasswordHelper()
    async with async_session_maker() as db:
        r = await db.execute(select(User).where(User.email == legacy))
        u = r.scalars().first()
        if not u:
            return
        conflict = await db.execute(select(User).where(User.email == login))
        existing_login = conflict.scalars().first()
        if existing_login is not None and existing_login.id != u.id:
            print(f"[skip-migrate] {legacy} -> {login}: target login already exists")
            return
        u.email = login
        u.hashed_password = ph.hash(password)
        u.role = "student"
        u.is_active = True
        u.is_verified = True
        u.display_name = display
        await db.commit()
        print(f"[migrate] {legacy} -> {login} display_name={display!r}")


async def main() -> None:
    for i in range(1, 11):
        login = _login_id(i)
        display = f"蚵間老師{DISPLAY_ZH[i - 1]}"
        await _migrate_legacy_to_login(i, login, display, DEFAULT_PASSWORD)
        await _ensure_user(
            email=login,
            password=DEFAULT_PASSWORD,
            role="student",
            display_name=display,
        )
    print("[done] 10 students; logins kejian01..kejian10; password:", DEFAULT_PASSWORD)


if __name__ == "__main__":
    asyncio.run(main())
