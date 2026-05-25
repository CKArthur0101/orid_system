import uuid

import pytest
from fastapi_users.password import PasswordHelper

from app.models import ClassRoom, User


@pytest.fixture
async def admin_user(db_session):
    ph = PasswordHelper()
    user = User(
        id=uuid.uuid4(),
        email="admin@test.local",
        hashed_password=ph.hash("AdminPass1"),
        is_active=True,
        is_superuser=True,
        is_verified=True,
        role="admin",
        display_name="Test Admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    from app.users import get_jwt_strategy

    token = await get_jwt_strategy().write_token(user)
    return {"user": user, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
async def demo_class(db_session):
    cls = ClassRoom(name="Test Class", year=2026, external_code="test-class")
    db_session.add(cls)
    await db_session.commit()
    await db_session.refresh(cls)
    return cls


@pytest.mark.asyncio(loop_scope="function")
async def test_admin_users_forbidden_for_student(test_client, authenticated_user):
    r = await test_client.get("/admin/users", headers=authenticated_user["headers"])
    assert r.status_code == 403


@pytest.mark.asyncio(loop_scope="function")
async def test_admin_create_student_with_class(test_client, admin_user, demo_class):
    r = await test_client.post(
        "/admin/users",
        headers=admin_user["headers"],
        json={
            "email": "newstudent01",
            "password": "Student01",
            "display_name": "新學生",
            "role": "student",
            "class_ids": [str(demo_class.id)],
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["password_once"] == "Student01"
    assert "hashed_password" not in data["user"]
    assert data["user"]["class_names"] == ["Test Class"]

    login = await test_client.post(
        "/auth/jwt/login",
        data={"username": "newstudent01", "password": "Student01"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio(loop_scope="function")
async def test_admin_reset_password(test_client, admin_user, db_session):
    ph = PasswordHelper()
    st = User(
        id=uuid.uuid4(),
        email="resetme01",
        hashed_password=ph.hash("OldPass1"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="student",
    )
    db_session.add(st)
    await db_session.commit()

    r = await test_client.patch(
        f"/admin/users/{st.id}",
        headers=admin_user["headers"],
        json={"new_password": "NewPass2"},
    )
    assert r.status_code == 200
    assert r.json()["password_once"] == "NewPass2"

    login = await test_client.post(
        "/auth/jwt/login",
        data={"username": "resetme01", "password": "NewPass2"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio(loop_scope="function")
async def test_admin_list_users_no_password_hash(test_client, admin_user, authenticated_user):
    r = await test_client.get("/admin/users", headers=admin_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert "hashed_password" not in item
        assert "password" not in item


@pytest.mark.asyncio(loop_scope="function")
async def test_admin_cannot_create_admin_role(test_client, admin_user):
    r = await test_client.post(
        "/admin/users",
        headers=admin_user["headers"],
        json={
            "email": "badadmin",
            "password": "BadAdmin1",
            "role": "admin",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio(loop_scope="function")
async def test_admin_create_class(test_client, admin_user):
    r = await test_client.post(
        "/admin/classes",
        headers=admin_user["headers"],
        json={"name": "DILAB2", "year": 2026, "external_code": "dilab2"},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "DILAB2"
