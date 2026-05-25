import uuid
import re
import logging

from typing import Optional

from fastapi import Depends, Request
from fastapi_users import (
    BaseUserManager,
    FastAPIUsers,
    UUIDIDMixin,
    InvalidPasswordException,
)

from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase

from .config import settings
from .database import get_user_db
from .email import send_reset_password_email
from .models import User
from .schemas import UserCreate

AUTH_URL_PATH = "auth"
logger = logging.getLogger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.RESET_PASSWORD_SECRET_KEY
    verification_token_secret = settings.VERIFICATION_SECRET_KEY

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info("User registered", extra={"user_id": str(user.id)})

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        await send_reset_password_email(user, token)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info("Verification requested", extra={"user_id": str(user.id)})

    async def create(
        self,
        user_create: UserCreate,
        safe: bool = False,
        request: Optional[Request] = None,
    ) -> User:
        """Public registration always creates student accounts."""
        user_dict = user_create.create_update_dict()
        user_dict["role"] = "student"
        user_create = UserCreate(**user_dict)
        return await super().create(user_create, safe, request)

    async def validate_password(
        self,
        password: str,
        user: UserCreate,
    ) -> None:
        errors = []

        if len(password) < 6:
            errors.append("Password should be at least 6 characters.")
        acct = (user.email or "").strip()
        if acct and acct == password:
            errors.append("Password should not be the same as your login id.")
        if not re.search(r"[A-Za-z]", password):
            errors.append("Password should contain at least one letter.")
        if not re.search(r"[0-9]", password):
            errors.append("Password should contain at least one number.")
        if not re.fullmatch(r"[A-Za-z0-9]+", password):
            errors.append("Password should contain only letters and numbers.")

        if errors:
            raise InvalidPasswordException(reason=errors)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl=f"{AUTH_URL_PATH}/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.ACCESS_SECRET_KEY,
        lifetime_seconds=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
