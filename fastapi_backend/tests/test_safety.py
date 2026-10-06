"""Tests for the layered, age-appropriate ORID safety classifier."""

from types import SimpleNamespace

import pytest

from app.services import safety
from app.models import OridSafetyEvent


class _FakeCategories:
    def __init__(self, **flags: bool):
        self._flags = flags

    def model_dump(self):
        return self._flags


class _FakeModerations:
    def __init__(self, categories: dict[str, bool]):
        self._categories = categories
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            results=[SimpleNamespace(categories=_FakeCategories(**self._categories))]
        )


class _FakeOpenAIClient:
    def __init__(self, categories: dict[str, bool]):
        self.moderations = _FakeModerations(categories)


def test_safety_event_model_does_not_duplicate_student_text():
    columns = set(OridSafetyEvent.__table__.columns.keys())
    assert "text_fingerprint" in columns
    assert "student_text" not in columns
    assert "content" not in columns


@pytest.mark.parametrize(
    "text",
    [
        "柿子樹的樹幹很粗。",
        "我在操場跑步。",
        "我喜歡做體操。",
        "請老師教我怎麼操作。",
        "他在故事裡很生氣。",
        "我看到有人把垃圾撿起來。",
        "我晚上九點上床睡覺。",
        "小時候我會跟媽媽上床睡覺。",
    ],
)
def test_local_safety_allows_ordinary_school_writing(text):
    decision = safety.classify_local_safety(text)
    assert decision.action == safety.SafetyAction.ALLOW
    assert decision.level == 0


@pytest.mark.parametrize("text", ["媽的", "靠邀", "幹", "幹你娘", "操你媽", "f.u.c.k", "shit"])
def test_local_safety_coaches_profanity_rephrase(text):
    decision = safety.classify_local_safety(text)
    assert decision.action == safety.SafetyAction.COACH_REPHRASE
    assert decision.level == 1
    assert decision.category == "profanity"


def test_local_safety_blocks_targeted_attack():
    decision = safety.classify_local_safety("你真是白痴")
    assert decision.action == safety.SafetyAction.BLOCK_AND_REWRITE
    assert decision.level == 2
    assert decision.category == "harassment"


def test_local_safety_blocks_threat():
    decision = safety.classify_local_safety("我要打死你")
    assert decision.action == safety.SafetyAction.BLOCK_AND_REWRITE
    assert decision.level == 3
    assert decision.category == "threat"


@pytest.mark.parametrize(
    "text",
    [
        "跟阿松爺爺上床",
        "我想和他上床",
        "他們發生性關係",
        "傳裸照給別人",
    ],
)
def test_local_safety_blocks_sexual_or_private_content(text):
    decision = safety.classify_local_safety(text)
    assert decision.action == safety.SafetyAction.BLOCK_AND_REWRITE
    assert decision.level == 3
    assert decision.category == "sexual_content"
    assert "性暗示或私密內容" in decision.student_message


def test_local_safety_supports_and_escalates_first_person_crisis():
    decision = safety.classify_local_safety("我真的不想活了")
    assert decision.action == safety.SafetyAction.SUPPORT_AND_ESCALATE
    assert decision.level == 4
    assert "信任的老師或大人" in decision.student_message


@pytest.mark.asyncio(loop_scope="function")
async def test_cloud_moderation_runs_for_writing_coach(monkeypatch):
    fake = _FakeOpenAIClient({"harassment": True})
    monkeypatch.setattr(safety, "client", fake)

    decision = await safety.classify_safety("這是一句沒有本地關鍵字的攻擊", writing_coach=True)

    assert decision.level == 2
    assert decision.provider == "moderation"
    assert fake.moderations.calls[0]["model"] == "omni-moderation-latest"


@pytest.mark.asyncio(loop_scope="function")
async def test_plain_story_violence_is_not_blocked_in_writing_coach(monkeypatch):
    fake = _FakeOpenAIClient({"violence": True})
    monkeypatch.setattr(safety, "client", fake)

    decision = await safety.classify_safety("故事裡的角色打了一架", writing_coach=True)

    assert decision.action == safety.SafetyAction.ALLOW


@pytest.mark.asyncio(loop_scope="function")
async def test_cloud_self_harm_uses_support_and_escalate(monkeypatch):
    fake = _FakeOpenAIClient({"self_harm_intent": True})
    monkeypatch.setattr(safety, "client", fake)

    decision = await safety.classify_safety("我不知道怎麼形容現在的狀況", writing_coach=True)

    assert decision.level == 4
    assert decision.action == safety.SafetyAction.SUPPORT_AND_ESCALATE


@pytest.mark.asyncio(loop_scope="function")
async def test_legacy_check_safety_wrapper_remains_compatible(monkeypatch):
    monkeypatch.setattr(safety, "client", None)

    is_unsafe, reason = await safety.check_safety("你白痴", writing_coach=True)

    assert is_unsafe is True
    assert "人身攻擊" in reason
