from __future__ import annotations

import re
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_users.password import PasswordHelper
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from datetime import timezone

from app.models import (
    ClassRoom,
    Item,
    OridBadgeEvent,
    OridChatMessage,
    OridFeedbackEvent,
    OridPostTestScore,
    OridSession,
    OridStageAttempt,
    OridWeekSubmission,
    StudentClassMembership,
    TeacherClassAssignment,
    User,
)
from app.schemas import (
    ADMIN_ASSIGNABLE_ROLES,
    AdminClassCreate,
    AdminClassSummary,
    AdminClassUpdate,
    AdminUserCreate,
    AdminUserCreateResponse,
    AdminUserDetail,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserUpdate,
    AdminUserUpdateResponse,
)
from app.users import current_active_user

router = APIRouter(tags=["admin"])
_password_helper = PasswordHelper()


def _user_role(user: User) -> str:
    return str(getattr(user, "role", "student") or "student").strip().lower()


async def require_admin(user: User = Depends(current_active_user)) -> User:
    if _user_role(user) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def validate_admin_password(password: str) -> None:
    errors: list[str] = []
    if len(password) < 6:
        errors.append("Password should be at least 6 characters.")
    if not re.search(r"[A-Za-z]", password):
        errors.append("Password should contain at least one letter.")
    if not re.search(r"[0-9]", password):
        errors.append("Password should contain at least one number.")
    if not re.fullmatch(r"[A-Za-z0-9]+", password):
        errors.append("Password should contain only letters and numbers.")
    if errors:
        raise HTTPException(status_code=400, detail={"password": errors})


async def _get_class_map(db: AsyncSession) -> dict[UUID, ClassRoom]:
    rows = await db.execute(select(ClassRoom))
    return {c.id: c for c in rows.scalars().all()}


async def _class_names_for_user(
    db: AsyncSession,
    user_id: UUID,
    role: str,
) -> tuple[list[UUID], list[str]]:
    cls_map = await _get_class_map(db)
    if role == "student":
        q = await db.execute(
            select(StudentClassMembership.class_id).where(
                StudentClassMembership.student_id == user_id
            )
        )
    elif role == "teacher":
        q = await db.execute(
            select(TeacherClassAssignment.class_id).where(
                TeacherClassAssignment.teacher_id == user_id
            )
        )
    else:
        return [], []
    ids = list(q.scalars().all())
    names = [cls_map[cid].name for cid in ids if cid in cls_map]
    return ids, names


def _user_orid_condition(user: User) -> str:
    return str(getattr(user, "orid_condition", "experimental") or "experimental").strip().lower()


def _user_to_list_item(
    user: User,
    class_ids: list[UUID],
    class_names: list[str],
) -> AdminUserListItem:
    return AdminUserListItem(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=_user_role(user),
        is_active=bool(user.is_active),
        orid_condition=_user_orid_condition(user),
        class_ids=class_ids,
        class_names=class_names,
    )


def _user_to_detail(
    user: User,
    class_ids: list[UUID],
    class_names: list[str],
) -> AdminUserDetail:
    return AdminUserDetail(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=_user_role(user),
        is_active=bool(user.is_active),
        is_verified=bool(user.is_verified),
        is_superuser=bool(user.is_superuser),
        orid_condition=_user_orid_condition(user),
        class_ids=class_ids,
        class_names=class_names,
    )


async def _ensure_classes_exist(db: AsyncSession, class_ids: list[UUID]) -> None:
    if not class_ids:
        return
    q = await db.execute(select(ClassRoom.id).where(ClassRoom.id.in_(class_ids)))
    found = set(q.scalars().all())
    missing = [str(cid) for cid in class_ids if cid not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown class_ids: {', '.join(missing)}")


async def _sync_user_classes(
    db: AsyncSession,
    user: User,
    role: str,
    class_ids: list[UUID],
) -> None:
    await _ensure_classes_exist(db, class_ids)
    uid = user.id
    if role == "student":
        await db.execute(delete(StudentClassMembership).where(StudentClassMembership.student_id == uid))
        await db.execute(delete(TeacherClassAssignment).where(TeacherClassAssignment.teacher_id == uid))
        for cid in class_ids:
            db.add(StudentClassMembership(student_id=uid, class_id=cid))
    elif role == "teacher":
        await db.execute(delete(TeacherClassAssignment).where(TeacherClassAssignment.teacher_id == uid))
        await db.execute(delete(StudentClassMembership).where(StudentClassMembership.student_id == uid))
        for cid in class_ids:
            db.add(TeacherClassAssignment(teacher_id=uid, class_id=cid))
    else:
        await db.execute(delete(StudentClassMembership).where(StudentClassMembership.student_id == uid))
        await db.execute(delete(TeacherClassAssignment).where(TeacherClassAssignment.teacher_id == uid))


async def _delete_user_cascade(db: AsyncSession, user_id: UUID) -> None:
    await db.execute(delete(OridBadgeEvent).where(OridBadgeEvent.user_id == user_id))
    await db.execute(delete(OridFeedbackEvent).where(OridFeedbackEvent.user_id == user_id))
    await db.execute(delete(OridStageAttempt).where(OridStageAttempt.user_id == user_id))
    await db.execute(
        delete(OridChatMessage).where(
            OridChatMessage.session_id.in_(
                select(OridSession.id).where(OridSession.user_id == user_id)
            )
        )
    )
    await db.execute(delete(OridWeekSubmission).where(OridWeekSubmission.user_id == user_id))
    await db.execute(delete(OridSession).where(OridSession.user_id == user_id))
    await db.execute(
        delete(OridPostTestScore).where(
            or_(
                OridPostTestScore.student_id == user_id,
                OridPostTestScore.grader_id == user_id,
            )
        )
    )
    await db.execute(delete(StudentClassMembership).where(StudentClassMembership.student_id == user_id))
    await db.execute(delete(TeacherClassAssignment).where(TeacherClassAssignment.teacher_id == user_id))
    await db.execute(delete(Item).where(Item.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))


@router.get("/users", response_model=AdminUserListResponse)
async def admin_list_users(
    q: str | None = Query(None, description="Search login or display_name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(require_admin),
):
    stmt = select(User)
    if q and (term := q.strip()):
        like = f"%{term}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.display_name.ilike(like)))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await db.execute(count_stmt)).scalar() or 0)
    stmt = stmt.order_by(User.email.asc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    items: list[AdminUserListItem] = []
    for u in rows:
        cids, cnames = await _class_names_for_user(db, u.id, _user_role(u))
        items.append(_user_to_list_item(u, cids, cnames))
    return AdminUserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def admin_get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(require_admin),
):
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    cids, cnames = await _class_names_for_user(db, u.id, _user_role(u))
    return _user_to_detail(u, cids, cnames)


@router.post("/users", response_model=AdminUserCreateResponse, status_code=201)
async def admin_create_user(
    data: AdminUserCreate,
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(require_admin),
):
    validate_admin_password(data.password)
    existing = await db.execute(select(User.id).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Login id already exists")
    user = User(
        id=uuid.uuid4(),
        email=data.email,
        hashed_password=_password_helper.hash(data.password),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role=data.role,
        display_name=data.display_name,
        orid_condition=data.orid_condition,
    )
    db.add(user)
    await db.flush()
    await _sync_user_classes(db, user, data.role, data.class_ids)
    await db.commit()
    await db.refresh(user)
    cids, cnames = await _class_names_for_user(db, user.id, data.role)
    return AdminUserCreateResponse(
        user=_user_to_detail(user, cids, cnames),
        password_once=data.password,
    )


@router.patch("/users/{user_id}", response_model=AdminUserUpdateResponse)
async def admin_update_user(
    user_id: UUID,
    data: AdminUserUpdate,
    db: AsyncSession = Depends(get_async_session),
    admin: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and data.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    password_once: str | None = None
    if data.email is not None and data.email != user.email:
        conflict = await db.execute(select(User.id).where(User.email == data.email, User.id != user_id))
        if conflict.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Login id already exists")
        user.email = data.email
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.role is not None:
        if _user_role(user) == "admin":
            raise HTTPException(status_code=400, detail="Cannot change admin role via API")
        user.role = data.role
    if data.orid_condition is not None:
        from datetime import datetime
        user.orid_condition = data.orid_condition
        user.orid_condition_updated_at = datetime.now(tz=timezone.utc)
    if data.new_password:
        validate_admin_password(data.new_password)
        user.hashed_password = _password_helper.hash(data.new_password)
        password_once = data.new_password
    role = _user_role(user)
    if data.class_ids is not None:
        await _sync_user_classes(db, user, role, data.class_ids)
    elif data.role is not None:
        await _sync_user_classes(db, user, role, [])
    await db.commit()
    await db.refresh(user)
    cids, cnames = await _class_names_for_user(db, user.id, role)
    return AdminUserUpdateResponse(user=_user_to_detail(user, cids, cnames), password_once=password_once)


@router.delete("/users/{user_id}", status_code=204)
async def admin_delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await _delete_user_cascade(db, user_id)
    await db.commit()


@router.get("/classes", response_model=list[AdminClassSummary])
async def admin_list_classes(
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(require_admin),
):
    classes = (await db.execute(select(ClassRoom).order_by(ClassRoom.name.asc()))).scalars().all()
    out: list[AdminClassSummary] = []
    for cls in classes:
        sc = await db.scalar(
            select(func.count())
            .select_from(StudentClassMembership)
            .where(StudentClassMembership.class_id == cls.id)
        )
        tc = await db.scalar(
            select(func.count())
            .select_from(TeacherClassAssignment)
            .where(TeacherClassAssignment.class_id == cls.id)
        )
        out.append(
            AdminClassSummary(
                id=cls.id,
                name=cls.name,
                year=cls.year,
                external_code=cls.external_code,
                student_count=int(sc or 0),
                teacher_count=int(tc or 0),
            )
        )
    return out


@router.post("/classes", response_model=AdminClassSummary, status_code=201)
async def admin_create_class(
    data: AdminClassCreate,
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(require_admin),
):
    cls = ClassRoom(
        id=uuid.uuid4(),
        name=data.name,
        year=data.year,
        external_code=data.external_code,
    )
    db.add(cls)
    await db.commit()
    await db.refresh(cls)
    return AdminClassSummary(
        id=cls.id,
        name=cls.name,
        year=cls.year,
        external_code=cls.external_code,
        student_count=0,
        teacher_count=0,
    )


@router.patch("/classes/{class_id}", response_model=AdminClassSummary)
async def admin_update_class(
    class_id: UUID,
    data: AdminClassUpdate,
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(require_admin),
):
    cls = await db.get(ClassRoom, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    if data.name is not None:
        cls.name = data.name.strip()
    if data.year is not None:
        cls.year = data.year
    if data.external_code is not None:
        cls.external_code = data.external_code.strip() or None
    await db.commit()
    await db.refresh(cls)
    sc = await db.scalar(
        select(func.count())
        .select_from(StudentClassMembership)
        .where(StudentClassMembership.class_id == cls.id)
    )
    tc = await db.scalar(
        select(func.count())
        .select_from(TeacherClassAssignment)
        .where(TeacherClassAssignment.class_id == cls.id)
    )
    return AdminClassSummary(
        id=cls.id,
        name=cls.name,
        year=cls.year,
        external_code=cls.external_code,
        student_count=int(sc or 0),
        teacher_count=int(tc or 0),
    )


@router.delete("/classes/{class_id}", status_code=204)
async def admin_delete_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(require_admin),
):
    cls = await db.get(ClassRoom, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    sc = await db.scalar(
        select(func.count())
        .select_from(StudentClassMembership)
        .where(StudentClassMembership.class_id == class_id)
    )
    tc = await db.scalar(
        select(func.count())
        .select_from(TeacherClassAssignment)
        .where(TeacherClassAssignment.class_id == class_id)
    )
    if (sc or 0) > 0 or (tc or 0) > 0:
        raise HTTPException(status_code=400, detail="Class has members; remove assignments first")
    await db.delete(cls)
    await db.commit()
