import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import quote, urlparse

from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from dotenv import load_dotenv

# Alembic may run with cwd != project root; ensure `app` imports.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_root_str = str(_REPO_ROOT)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

load_dotenv()

from app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_database_url() -> str:
    """Use DATABASE_URL, or build asyncpg URL from POSTGRES_* (Docker + compose env_file)."""
    direct = os.getenv("DATABASE_URL")
    if direct and direct.strip():
        return direct.strip()
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    dbname = os.getenv("POSTGRES_DB")
    if user and password and dbname:
        default_host = "db" if os.path.exists("/.dockerenv") else "localhost"
        _h = os.getenv("POSTGRES_HOST")
        host = (_h.strip() if _h else "") or default_host
        _p = os.getenv("POSTGRES_PORT")
        port = (_p.strip() if _p else "") or "5432"
        return (
            "postgresql+asyncpg://"
            + quote(user, safe="")
            + ":"
            + quote(password, safe="")
            + f"@{host}:{port}/"
            + quote(dbname, safe="")
        )
    raise ValueError(
        "DATABASE_URL is not set. Set it, or set POSTGRES_USER, POSTGRES_PASSWORD, and "
        "POSTGRES_DB (optional POSTGRES_HOST / POSTGRES_PORT; host defaults to db in Docker, "
        "else localhost)."
    )


database_url = _resolve_database_url()

if database_url.startswith("postgresql://") and "+asyncpg" not in database_url.split(":", 1)[0]:
    sqlalchemy_url = "postgresql+asyncpg://" + database_url.split("://", 1)[1]
elif database_url.startswith("postgresql+asyncpg://"):
    sqlalchemy_url = database_url
else:
    parsed = urlparse(database_url)
    u, p = parsed.username or "", parsed.password or ""
    host = parsed.hostname or "localhost"
    port = parsed.port
    port_part = f":{port}" if port else ""
    path = parsed.path or "/"
    sqlalchemy_url = (
        f"postgresql+asyncpg://{quote(u, safe='')}:{quote(p, safe='')}"
        f"@{host}{port_part}{path}"
    )

config.set_main_option("sqlalchemy.url", sqlalchemy_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
