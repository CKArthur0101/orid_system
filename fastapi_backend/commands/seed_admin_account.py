"""
建立專用管理後台帳號 orid_admin（role=admin, is_superuser=True）。

執行（prod 範例）：

  docker compose -p orid-prod -f docker-compose.prod.yml exec -T backend sh -c \\
    "export DATABASE_URL='postgresql+asyncpg://postgres:PASS@db:5432/orid_prod' && \\
     uv run python commands/seed_admin_account.py"
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

ADMIN_LOGIN = "orid_admin"
ADMIN_DISPLAY = "ORID 管理員"
DEFAULT_PASSWORD = "OridAdmin2026"


async def main() -> None:
    ph = PasswordHelper()
    async with async_session_maker() as db:
        r = await db.execute(select(User).where(User.email == ADMIN_LOGIN))
        u = r.scalars().first()
        if u:
            u.hashed_password = ph.hash(DEFAULT_PASSWORD)
            u.role = "admin"
            u.is_active = True
            u.is_verified = True
            u.is_superuser = True
            u.display_name = ADMIN_DISPLAY
            await db.commit()
            print(f"[update] {ADMIN_LOGIN} role=admin")
        else:
            u = User(
                id=uuid.uuid4(),
                email=ADMIN_LOGIN,
                hashed_password=ph.hash(DEFAULT_PASSWORD),
                is_active=True,
                is_superuser=True,
                is_verified=True,
                role="admin",
                display_name=ADMIN_DISPLAY,
            )
            db.add(u)
            await db.commit()
            print(f"[create] {ADMIN_LOGIN} role=admin")
        print(f"[done] login={ADMIN_LOGIN!r} password={DEFAULT_PASSWORD!r} (請登入後立即修改)")


if __name__ == "__main__":
    asyncio.run(main())
