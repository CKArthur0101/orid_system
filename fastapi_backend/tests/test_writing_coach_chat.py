"""Integration tests for POST /orid/writing-coach/chat (control path, no LLM)."""

import json

import pytest
from sqlalchemy import select

from app.models import OridChatMessage, OridSession, Reading


def _minimal_book_pack() -> str:
    return json.dumps(
        {
            "schema": "book_pack_v1",
            "version": 999,
            "book_title": "單元測試用書",
            "characters": [{"name": "阿松爺爺", "role": "故事角色"}],
            "key_events": ["測試事件一"],
        },
        ensure_ascii=False,
    )


@pytest.mark.asyncio(loop_scope="function")
async def test_writing_coach_control_feedback_button_persists_messages(
    test_client, db_session, authenticated_user
):
    user = authenticated_user["user"]
    reading = Reading(title="第1週 測試", content=_minimal_book_pack())
    db_session.add(reading)
    await db_session.commit()
    await db_session.refresh(reading)

    session = OridSession(
        user_id=user.id,
        reading_id=reading.id,
        condition="control",
        current_stage="O",
        stage_turn=0,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    draft = "故事裡阿松爺爺把柿子藏起來。他後來很難過。"
    r = await test_client.post(
        "/orid/writing-coach/chat",
        json={
            "session_id": str(session.id),
            "student_text": draft,
            "stage": "O",
            "draft": "d1",
            "source": "feedback_button",
            "week": 1,
            "save_feedback": False,
        },
        headers=authenticated_user["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_id"] == str(session.id)
    assert data["ai_reply"].strip()
    assert data["meta"].get("source") == "feedback_button"
    assert data["meta"].get("condition") == "control"

    q = await db_session.execute(
        select(OridChatMessage).where(OridChatMessage.session_id == session.id).order_by(OridChatMessage.created_at.asc())
    )
    rows = list(q.scalars().all())
    assert len(rows) == 2
    assert rows[0].sender == "student"
    assert "[O" in rows[0].text and draft in rows[0].text
    assert rows[1].sender == "ai"
    assert rows[1].text.strip() == data["ai_reply"].strip()


@pytest.mark.asyncio(loop_scope="function")
async def test_writing_coach_control_free_text(test_client, db_session, authenticated_user):
    user = authenticated_user["user"]
    reading = Reading(title="第2週 測試", content=_minimal_book_pack())
    db_session.add(reading)
    await db_session.commit()
    await db_session.refresh(reading)

    session = OridSession(
        user_id=user.id,
        reading_id=reading.id,
        condition="control",
        current_stage="R",
        stage_turn=0,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    r = await test_client.post(
        "/orid/writing-coach/chat",
        json={
            "session_id": str(session.id),
            "student_text": "這樣寫可以嗎？",
            "stage": "R",
            "draft": "d1",
            "source": "free_text",
            "week": 2,
            "save_feedback": False,
        },
        headers=authenticated_user["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ai_reply"].strip()
    assert data["meta"].get("source") == "free_text"


@pytest.mark.asyncio(loop_scope="function")
async def test_writing_coach_rejects_empty_free_text(test_client, db_session, authenticated_user):
    user = authenticated_user["user"]
    reading = Reading(title="第3週 測試", content=_minimal_book_pack())
    db_session.add(reading)
    await db_session.commit()
    await db_session.refresh(reading)

    session = OridSession(
        user_id=user.id,
        reading_id=reading.id,
        condition="control",
        current_stage="O",
        stage_turn=0,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    r = await test_client.post(
        "/orid/writing-coach/chat",
        json={
            "session_id": str(session.id),
            "student_text": "   ",
            "stage": "O",
            "draft": "d1",
            "source": "free_text",
            "week": 3,
            "save_feedback": False,
        },
        headers=authenticated_user["headers"],
    )
    assert r.status_code == 400

@pytest.mark.asyncio(loop_scope="function")
async def test_writing_coach_control_flags_content_not_in_book_pack(
    test_client, db_session, authenticated_user
):
    """Control path must still surface book-grounding (not only GenAI)."""
    user = authenticated_user["user"]
    reading = Reading(title="第四週 測試", content=_minimal_book_pack())
    db_session.add(reading)
    await db_session.commit()
    await db_session.refresh(reading)

    session = OridSession(
        user_id=user.id,
        reading_id=reading.id,
        condition="control",
        current_stage="O",
        stage_turn=0,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    draft = "我看到爺爺跟curry打籃球"
    r = await test_client.post(
        "/orid/writing-coach/chat",
        json={
            "session_id": str(session.id),
            "student_text": draft,
            "stage": "O",
            "draft": "d1",
            "source": "feedback_button",
            "week": 1,
            "save_feedback": False,
        },
        headers=authenticated_user["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "對齊教材" in data["ai_reply"]


@pytest.mark.asyncio(loop_scope="function")
async def test_writing_coach_control_flags_unsupported_character_event(
    test_client, db_session, authenticated_user
):
    """A book character plus an unsupported event should not be treated as grounded."""
    user = authenticated_user["user"]
    reading = Reading(title="第五週 測試", content=_minimal_book_pack())
    db_session.add(reading)
    await db_session.commit()
    await db_session.refresh(reading)

    session = OridSession(
        user_id=user.id,
        reading_id=reading.id,
        condition="control",
        current_stage="O",
        stage_turn=0,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    r = await test_client.post(
        "/orid/writing-coach/chat",
        json={
            "session_id": str(session.id),
            "student_text": "爺爺過世",
            "stage": "O",
            "draft": "d1",
            "source": "feedback_button",
            "week": 1,
            "save_feedback": False,
        },
        headers=authenticated_user["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "對齊教材" in data["ai_reply"]
    assert "過世" not in str(data.get("feedback_praise") or "")

