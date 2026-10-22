"""Pre-deploy checks against the isolated test database. No production connection."""
from __future__ import annotations

import json
import uuid
import zipfile
from datetime import timedelta
from io import BytesIO
from xml.sax.saxutils import escape

import pytest
from fastapi_users.password import PasswordHelper
from sqlalchemy import func, select

from app.models import ClassRoom, OridChatMessage, OridSession, OridWeekSubmission, User
from app.users import get_jwt_strategy

CLASS_COUNTS = {
    "1": 31,
    "2": 31,
    "3": 31,
    "4": 30,
    "5": 32,
    "6": 30,
    "7": 31,
    "8": 31,
    "9": 30,
}


def _xlsx(rows: list[tuple[str, str, str, str]]) -> bytes:
    shared: list[str] = []
    index: dict[str, int] = {}

    def sid(value: str) -> int:
        if value not in index:
            index[value] = len(shared)
            shared.append(value)
        return index[value]

    body = []
    for row_no, row in enumerate(rows, start=1):
        cells = []
        for col_no, value in enumerate(row, start=1):
            column = chr(64 + col_no)
            cells.append(f'<c r="{column}{row_no}" t="s"><v>{sid(value)}</v></c>')
        body.append(f'<row r="{row_no}">{"".join(cells)}</row>')
    shared_xml = "".join(f"<si><t>{escape(item)}</t></si>" for item in shared)
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    files = {
        "xl/sharedStrings.xml": (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<sst xmlns="{ns}" count="{len(shared)}" uniqueCount="{len(shared)}">{shared_xml}</sst>'
        ),
        "xl/worksheets/sheet1.xml": (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<worksheet xmlns="{ns}"><sheetData>{"".join(body)}</sheetData></worksheet>'
        ),
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as workbook:
        for name, text in files.items():
            workbook.writestr(name, text)
    return buffer.getvalue()


def _full_roster() -> list[tuple[str, str, str, str]]:
    rows = []
    for class_no, count in CLASS_COUNTS.items():
        for seat in range(1, count + 1):
            rows.append((f"測生{class_no}-{seat:02d}", "5", class_no, str(seat)))
    return rows


def _sample_roster() -> list[tuple[str, str, str, str]]:
    return [
        ("測生甲", "5", "1", "10"),
        ("測生乙", "5", "1", "1"),
        ("測生丙", "5", "2", "2"),
    ]


@pytest.fixture
async def admin_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email="predeploy-admin",
        hashed_password=PasswordHelper().hash("AdminPass1"),
        is_active=True,
        is_superuser=True,
        is_verified=True,
        role="admin",
        display_name="部署前管理員",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = await get_jwt_strategy().write_token(user)
    return {"user": user, "headers": {"Authorization": f"Bearer {token}"}}


def _upload(payload: bytes):
    return {
        "file": (
            "roster.xlsx",
            payload,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


async def _bearer(test_client, username: str, password: str) -> dict[str, str]:
    response = await test_client.post(
        "/auth/jwt/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio(loop_scope="function")
async def test_dry_run_reports_eight_classes_and_rejects_bad_rows(test_client, admin_user):
    response = await test_client.post(
        "/admin/experiment/dry-run",
        headers=admin_user["headers"],
        files=_upload(_xlsx(_full_roster())),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["students_to_create"] == 246
    assert body["teachers_to_create"] == 8
    assert body["skipped_507"] == 31
    assert [item["code"] for item in body["classes"]] == [
        "501",
        "502",
        "503",
        "504",
        "505",
        "506",
        "508",
        "509",
    ]
    counts = {item["code"]: item["students"] for item in body["classes"]}
    assert counts == {
        "501": 31,
        "502": 31,
        "503": 31,
        "504": 30,
        "505": 32,
        "506": 30,
        "508": 31,
        "509": 30,
    }
    assert body["classes"][0]["study_condition"] == "experimental"
    assert body["classes"][1]["study_condition"] == "control"
    assert "測生" not in response.text

    duplicate = _sample_roster() + [("測生甲", "5", "1", "10")]
    bad = await test_client.post(
        "/admin/experiment/dry-run",
        headers=admin_user["headers"],
        files=_upload(_xlsx(duplicate + [("壞列", "4", "1", "3")])),
    )
    assert bad.status_code == 200
    problem = bad.json()
    assert problem["ok"] is False
    assert "duplicate_in_file" in problem["error_reasons"]
    assert "invalid_row" in problem["error_reasons"]
    assert "50110" in problem["error_logins"]


@pytest.mark.asyncio(loop_scope="function")
async def test_archive_keeps_dilab_and_hides_legacy_classes(test_client, admin_user):
    for name, code in (
        ("南勢國小", "Nanshih"),
        ("蚵間國小", "kejian-guo-xiao"),
        ("DILAB", "ky-solo-114524020"),
    ):
        created = await test_client.post(
            "/admin/classes",
            headers=admin_user["headers"],
            json={"name": name, "year": 2026, "external_code": code},
        )
        assert created.status_code == 201, created.text

    archived = await test_client.post(
        "/admin/experiment/archive-legacy",
        headers=admin_user["headers"],
    )
    assert archived.status_code == 200
    assert set(archived.json()["archived"]) == {"南勢國小", "蚵間國小"}

    visible = await test_client.get("/admin/classes", headers=admin_user["headers"])
    names = {item["name"] for item in visible.json()}
    assert "DILAB" in names
    assert "南勢國小" not in names
    assert "蚵間國小" not in names

    included = await test_client.get(
        "/admin/classes?include_archived=true",
        headers=admin_user["headers"],
    )
    by_name = {item["name"]: item for item in included.json()}
    assert by_name["南勢國小"]["archived_at"]
    assert by_name["蚵間國小"]["archived_at"]
    assert by_name["DILAB"]["archived_at"] is None

    again = await test_client.post(
        "/admin/classes/" + by_name["DILAB"]["id"] + "/archive",
        headers=admin_user["headers"],
    )
    assert again.status_code == 200
    hidden = await test_client.get("/admin/classes", headers=admin_user["headers"])
    assert all(item["name"] != "DILAB" for item in hidden.json())


@pytest.mark.asyncio(loop_scope="function")
async def test_import_accounts_teacher_scope_and_repeat_import(test_client, admin_user, db_session):
    payload = _xlsx(_sample_roster())
    imported = await test_client.post(
        "/admin/experiment/import",
        headers=admin_user["headers"],
        files=_upload(payload),
    )
    assert imported.status_code == 200, imported.text
    created = set(imported.json()["created_logins"])
    assert {"50101", "50110", "50202", "501teacher", "502teacher"} <= created
    assert "507" not in created
    assert "hashed_password" not in imported.text

    listed = await test_client.get("/admin/users?page_size=100", headers=admin_user["headers"])
    assert listed.status_code == 200
    assert "hashed_password" not in listed.text
    accounts = {item["email"]: item for item in listed.json()["items"]}
    assert accounts["50101"]["orid_condition"] == "experimental"
    assert accounts["50202"]["orid_condition"] == "control"
    assert accounts["50101"]["display_name"] == "測生乙"

    student_headers = await _bearer(test_client, "50101", "50101")
    control_headers = await _bearer(test_client, "50202", "50202")
    wrong = await test_client.post(
        "/auth/jwt/login",
        data={"username": "50101", "password": "other"},
    )
    assert wrong.status_code == 400

    me = await test_client.patch(
        "/users/me",
        headers=student_headers,
        json={"orid_condition": "control"},
    )
    assert me.status_code in {200, 422}
    current = await test_client.get("/users/me", headers=student_headers)
    assert current.json()["orid_condition"] == "experimental"

    experimental_session = await test_client.post(
        "/orid/sessions/ensure?week=1&condition=control",
        headers=student_headers,
    )
    assert experimental_session.status_code == 200, experimental_session.text
    assert experimental_session.json()["condition"] == "genai"
    control_session = await test_client.post(
        "/orid/sessions/ensure?week=1&condition=genai",
        headers=control_headers,
    )
    assert control_session.status_code == 200, control_session.text
    assert control_session.json()["condition"] == "control"

    teacher_headers = await _bearer(test_client, "501teacher", "501teacher")
    own_classes = await test_client.get("/teacher/me/classes", headers=teacher_headers)
    assert own_classes.status_code == 200
    assert len(own_classes.json()) == 1
    assert own_classes.json()[0]["external_code"] == "501"
    own_id = own_classes.json()[0]["id"]
    overview = await test_client.get(
        f"/teacher/classes/{own_id}/overview?week=1",
        headers=teacher_headers,
    )
    assert overview.status_code == 200, overview.text
    seats = [row["seat_no"] for row in overview.json()["students"]]
    emails = [row["student_email"] for row in overview.json()["students"]]
    assert seats == [1, 10]
    assert emails == ["50101", "50110"]

    other = await test_client.get("/teacher/me/classes", headers=await _bearer(test_client, "502teacher", "502teacher"))
    other_id = other.json()[0]["id"]
    denied = await test_client.get(
        f"/teacher/classes/{other_id}/overview?week=1",
        headers=teacher_headers,
    )
    assert denied.status_code == 403
    denied_research = await test_client.get(
        f"/teacher/classes/{other_id}/research-overview?week=1",
        headers=teacher_headers,
    )
    assert denied_research.status_code == 403
    other_student = next(item for item in accounts.values() if item["email"] == "50202")
    denied_summary = await test_client.get(
        f"/teacher/classes/{own_id}/students/{other_student['id']}/summary?week=1",
        headers=teacher_headers,
    )
    assert denied_summary.status_code == 404

    blocked = await test_client.post(
        "/orid/sessions",
        headers=teacher_headers,
        json={"reading_id": str(uuid.uuid4())},
    )
    assert blocked.status_code == 403

    student = (await db_session.execute(select(User).where(User.email == "50101"))).scalar_one()
    opened = experimental_session.json()
    existing = await db_session.get(OridSession, uuid.UUID(opened["id"]))
    assert existing is not None
    existing.current_stage = "R"
    spoke_at = existing.created_at + timedelta(milliseconds=20)
    db_session.add_all(
        [
            OridChatMessage(
                id=uuid.uuid4(),
                session_id=existing.id,
                stage="O",
                sender="student",
                text="我想寫觀察。",
                created_at=spoke_at,
            ),
            OridChatMessage(
                id=uuid.uuid4(),
                session_id=existing.id,
                stage="O",
                sender="ai",
                text="可以再寫得更具體。",
                created_at=spoke_at + timedelta(milliseconds=20),
            ),
        ]
    )
    db_session.add(
        OridWeekSubmission(
            id=uuid.uuid4(),
            user_id=student.id,
            reading_id=uuid.UUID(opened["reading_id"]),
            session_id=existing.id,
            week=1,
            content=json.dumps(
                {"stages": {"O": {"d1": "觀察一句"}, "R": {"d1": "感受一句"}, "I": {"d1": ""}, "D": {"d1": ""}}},
                ensure_ascii=False,
            ),
        )
    )
    await db_session.commit()
    summary = await test_client.get(
        f"/teacher/classes/{own_id}/students/{student.id}/summary?week=1",
        headers=teacher_headers,
    )
    assert summary.status_code == 200, summary.text
    detail = summary.json()
    assert detail["stage_texts"]["O"] == "觀察一句"
    assert detail["stage_texts"]["R"] == "感受一句"
    assert detail["writing_completed_stages"] == 2
    assert detail["interaction_count"] == 1, detail
    assert detail["current_stage"] == "R"

    before = await db_session.scalar(select(func.count()).select_from(User))
    again = await test_client.post(
        "/admin/experiment/import",
        headers=admin_user["headers"],
        files=_upload(payload),
    )
    assert again.status_code == 200, again.text
    assert again.json()["created_logins"] == []
    assert again.json()["students_to_create"] == 0
    after = await db_session.scalar(select(func.count()).select_from(User))
    assert after == before

    clash = await test_client.post(
        "/admin/experiment/import",
        headers=admin_user["headers"],
        files=_upload(_xlsx([("另一人", "5", "1", "1")])),
    )
    assert clash.status_code == 409
    assert "50101" in clash.json()["detail"]["conflict_logins"]
    unchanged = await test_client.get("/admin/users?q=50101", headers=admin_user["headers"])
    assert unchanged.json()["items"][0]["display_name"] == "測生乙"
    classes = await db_session.scalar(
        select(func.count()).select_from(ClassRoom).where(ClassRoom.external_code == "507")
    )
    assert classes == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_login_lock_is_per_account(test_client, db_session):
    user = User(
        id=uuid.uuid4(),
        email="lock-check",
        hashed_password=PasswordHelper().hash("LockPass1"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="student",
    )
    db_session.add(user)
    await db_session.commit()
    for _ in range(7):
        failed = await test_client.post(
            "/auth/jwt/login",
            data={"username": "lock-check", "password": "wrong"},
        )
        assert failed.status_code == 400
    locked = await test_client.post(
        "/auth/jwt/login",
        data={"username": "lock-check", "password": "wrong"},
    )
    assert locked.status_code == 429
    assert locked.json()["detail"] == "登入暫停，請稍後再試。"
    still = await test_client.post(
        "/auth/jwt/login",
        data={"username": "lock-check", "password": "LockPass1"},
    )
    assert still.status_code == 429
    other = await test_client.post(
        "/auth/jwt/login",
        data={"username": "missing-account", "password": "LockPass1"},
    )
    assert other.status_code == 400
