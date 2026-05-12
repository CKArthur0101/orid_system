from typing import AsyncGenerator

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import NullPool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .models import Base, User


def _build_async_database_url(raw_url: str) -> str:
    """
    Preserve the full DSN, including SSL / pooler query params used by managed
    Postgres providers such as Supabase, while normalizing the driver to asyncpg.
    """
    url = make_url(raw_url)
    driver = url.drivername
    if driver in {"postgres", "postgresql"}:
        driver = "postgresql+asyncpg"
    elif driver.startswith("postgresql+") and driver != "postgresql+asyncpg":
        driver = "postgresql+asyncpg"
    elif driver.startswith("postgres+") and driver != "postgresql+asyncpg":
        driver = "postgresql+asyncpg"
    # `str(URL)` masks the password as `***`, which breaks real DB connections.
    return url.set(drivername=driver).render_as_string(hide_password=False)


async_db_connection_url = _build_async_database_url(settings.DATABASE_URL)

engine_kwargs = {"pool_pre_ping": True}
if settings.DB_DISABLE_POOLING:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT_SEC,
            "pool_recycle": settings.DB_POOL_RECYCLE_SEC,
        }
    )

engine = create_async_engine(async_db_connection_url, **engine_kwargs)

async_session_maker = async_sessionmaker(
    engine, expire_on_commit=settings.EXPIRE_ON_COMMIT
)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)
