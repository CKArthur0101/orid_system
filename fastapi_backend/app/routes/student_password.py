"""One student-initiated password change for the experiment cohort."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models import User
from app.services.experiment_cohort import one_time_password_errors
from app.services.experiment_import import user_is_experiment_cohort
from app.users import current_active_user
from fastapi_users.password import PasswordHelper

router = APIRouter()
_password_helper = PasswordHelper()


class StudentPasswordStatus(BaseModel):
    eligible: bool
    locked: bool


class StudentPasswordChange(BaseModel):
    password: str = Field(max_length=128)


def _role(user: User) -> str:
    return str(getattr(user, "role", "student") or "student").strip().lower()


async def _eligible(db: AsyncSession, user: User) -> bool:
    if _role(user) != "student":
        return False
    return await user_is_experiment_cohort(db, user)


def _status(eligible: bool, user: User) -> StudentPasswordStatus:
    return StudentPasswordStatus(
        eligible=eligible,
        locked=bool(eligible and getattr(user, "password_change_used", False)),
    )


@router.get("/password-change", response_model=StudentPasswordStatus)
async def student_password_status(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    return _status(await _eligible(db, user), user)


@router.post("/password-change", response_model=StudentPasswordStatus)
async def student_password_change(
    data: StudentPasswordChange,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    if not await _eligible(db, user):
        raise HTTPException(status_code=403, detail="這個帳號不能在這裡修改密碼。")
    if getattr(user, "password_change_used", False):
        raise HTTPException(status_code=409, detail="已經修改過密碼。")
    password = data.password.strip()
    errors = one_time_password_errors(password)
    if errors:
        raise HTTPException(status_code=400, detail=errors[0])
    user.hashed_password = _password_helper.hash(password)
    user.password_visible = password
    user.password_change_used = True
    await db.commit()
    return _status(True, user)
