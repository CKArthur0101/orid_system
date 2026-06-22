import os
from typing import Self, Set
from urllib.parse import quote

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _database_url_from_postgres_env() -> str | None:
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    dbname = os.getenv("POSTGRES_DB")
    if not (user and password and dbname):
        return None
    default_host = "db" if os.path.exists("/.dockerenv") else "localhost"
    host = (os.getenv("POSTGRES_HOST") or "").strip() or default_host
    port = (os.getenv("POSTGRES_PORT") or "").strip() or "5432"
    return (
        "postgresql+asyncpg://"
        + quote(user, safe="")
        + ":"
        + quote(password, safe="")
        + f"@{host}:{port}/"
        + quote(dbname, safe="")
    )


class Settings(BaseSettings):
    # OpenAPI docs
    OPENAPI_URL: str = "/openapi.json"

    # Database
    DATABASE_URL: str | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None
    POSTGRES_HOST: str | None = None
    POSTGRES_PORT: str | None = None
    TEST_DATABASE_URL: str | None = None
    EXPIRE_ON_COMMIT: bool = False
    DB_DISABLE_POOLING: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT_SEC: int = 30
    DB_POOL_RECYCLE_SEC: int = 1800

    # User
    ACCESS_SECRET_KEY: str
    RESET_PASSWORD_SECRET_KEY: str
    VERIFICATION_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 12
    # When False, `/auth/register` and forgot/reset-password routes are not mounted (experiment / prod hardening).
    ENABLE_PUBLIC_REGISTRATION_AND_PASSWORD_RESET: bool = False

    # Email
    MAIL_USERNAME: str | None = None
    MAIL_PASSWORD: str | None = None
    MAIL_FROM: str | None = None
    MAIL_SERVER: str | None = None
    MAIL_PORT: int | None = None
    MAIL_FROM_NAME: str = "FastAPI template"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True
    TEMPLATE_DIR: str = "email_templates"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # CORS
    CORS_ORIGINS: Set[str]

    # ORID：逗號分隔「登入帳號」（學號或信箱），可使用「重新開始本週」(force_new)；空＝誰都不行
    ORID_FORCE_NEW_ALLOWLIST: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @model_validator(mode="after")
    def resolve_database_url(self) -> Self:
        if self.DATABASE_URL:
            return self
        built = _database_url_from_postgres_env()
        if built:
            object.__setattr__(self, "DATABASE_URL", built)
            return self
        raise ValueError(
            "DATABASE_URL is not set. Set it, or set POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB."
        )


settings = Settings()
