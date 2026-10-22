"""Login route with a per-account failure lock. Passwords are not logged or stored."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import BaseUserManager
from fastapi_users.authentication import Strategy
from fastapi_users.openapi import OpenAPIResponseType
from fastapi_users.router.common import ErrorCode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models import LoginLock, User
from app.services.login_lock import LockState, is_locked, record_failure, record_success
from app.users import auth_backend, get_user_manager

router = APIRouter()


def _state_from_row(row: LoginLock | None) -> LockState:
    if row is None:
        return LockState()
    return LockState(fail_count=int(row.fail_count or 0), locked_until=row.locked_until)


async def _load_lock(db: AsyncSession, login_id: str) -> LoginLock | None:
    result = await db.execute(select(LoginLock).where(LoginLock.login_id == login_id))
    return result.scalars().first()


async def _save_state(db: AsyncSession, login_id: str, state: LockState) -> None:
    row = await _load_lock(db, login_id)
    if state.fail_count == 0 and state.locked_until is None:
        if row is not None:
            await db.delete(row)
        return
    if row is None:
        row = LoginLock(login_id=login_id)
        db.add(row)
    row.fail_count = state.fail_count
    row.locked_until = state.locked_until
    row.updated_at = datetime.now(timezone.utc)


login_responses: OpenAPIResponseType = {
    status.HTTP_400_BAD_REQUEST: {"description": "Bad credentials or inactive user."},
    status.HTTP_429_TOO_MANY_REQUESTS: {"description": "This login is temporarily paused."},
}


@router.post("/login", name="auth:jwt.login_with_lock", responses=login_responses)
async def login(
    request: Request,
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: BaseUserManager[User, object] = Depends(get_user_manager),
    strategy: Strategy[User, object] = Depends(auth_backend.get_strategy),
    db: AsyncSession = Depends(get_async_session),
):
    login_id = (credentials.username or "").strip()
    now = datetime.now(timezone.utc)
    current = _state_from_row(await _load_lock(db, login_id))
    if login_id and is_locked(current, now):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="登入暫停，請稍後再試。")

    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        if login_id:
            updated = record_failure(current, now)
            await _save_state(db, login_id, updated)
            await db.commit()
            if is_locked(updated, now):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="登入暫停，請稍後再試。",
                )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.LOGIN_BAD_CREDENTIALS)

    if login_id:
        await _save_state(db, login_id, record_success())
        await db.commit()
    response = await auth_backend.login(strategy, user)
    await user_manager.on_after_login(user, request, response)
    return response
