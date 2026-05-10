from typing import Set

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # OpenAPI docs
    OPENAPI_URL: str = "/openapi.json"

    # Database
    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None
    EXPIRE_ON_COMMIT: bool = False

    # User
    ACCESS_SECRET_KEY: str
    RESET_PASSWORD_SECRET_KEY: str
    VERIFICATION_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24 * 365

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


settings = Settings()
