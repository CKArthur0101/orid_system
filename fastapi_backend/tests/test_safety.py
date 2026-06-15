"""Tests for app.services.safety.check_safety."""

from types import SimpleNamespace

import pytest

from app.services import safety


class _FakeCategories:
    def __init__(self, **flags: bool):
        self._flags = flags

    def model_dump(self):
        return self._flags


class _FakeModerationResult:
    def __init__(self, flagged: bool, categories: dict[str, bool]):
        self.flagged = flagged
        self.categories = _FakeCategories(**categories)


class _FakeModerations:
    def __init__(self, flagged: bool, categories: dict[str, bool]):
        self._flagged = flagged
        self._categories = categories

    async def create(self, input: str):
        return SimpleNamespace(
            results=[_FakeModerationResult(self._flagged, self._categories)]
        )


class _FakeOpenAIClient:
    def __init__(self, flagged: bool, categories: dict[str, bool]):
        self.moderations = _FakeModerations(flagged, categories)


@pytest.mark.asyncio(loop_scope="function")
async def test_check_safety_blocks_local_profanity_even_in_writing_coach(monkeypatch):
    monkeypatch.setattr(safety, "client", _FakeOpenAIClient(False, {}))

    unsafe, reason = await safety.check_safety("你白痴", writing_coach=True)

    assert unsafe is True
    assert "人身攻擊" in reason


@pytest.mark.asyncio(loop_scope="function")
async def test_check_safety_writing_coach_skips_cloud_moderation(monkeypatch):
    monkeypatch.setattr(
        safety,
        "client",
        _FakeOpenAIClient(True, {"violence": True}),
    )

    unsafe, reason = await safety.check_safety(
        "要做好人，因為爺爺打奶奶",
        writing_coach=True,
    )

    assert unsafe is False
    assert reason == ""


@pytest.mark.asyncio(loop_scope="function")
async def test_check_safety_strict_mode_uses_cloud_moderation(monkeypatch):
    monkeypatch.setattr(
        safety,
        "client",
        _FakeOpenAIClient(True, {"violence": True}),
    )

    unsafe, reason = await safety.check_safety("爺爺打奶奶", writing_coach=False)

    assert unsafe is True
    assert reason == "包含不當言論"
