"""
Tests for the experimental-group completion flow.

Covers:
- format_genai_completed_feedback_reply output format
- parseable by frontend-equivalent logic
- control group isolation: format_control_feedback_reply still produces revision format
- _looks_valid_feedback_narration accepts both complete and revision cards
- _apply_orid_rubric_ok_rule level 3/4 → fb_ok=True
- writing_feedback templates: no infinite-expansion on level 3/4
"""
from __future__ import annotations

import pytest

from app.prompts.policy.genai_completed_feedback import format_genai_completed_feedback_reply
from app.prompts.policy.control_feedback import format_control_feedback_reply


# ─────────────────────────────────────────────────────────────────────────────
# format_genai_completed_feedback_reply
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatGenaiCompletedFeedbackReply:
    """Deterministic completion message must use fixed headings and be free of modification language."""

    STAGES = ["O", "R", "I", "D"]

    def _parse_headings(self, text: str) -> dict[str, str]:
        """Simple heading extractor matching the frontend parser logic."""
        sections: dict[str, str] = {}
        HEADINGS = {
            "praise": "你已經做到：",
            "completion": "本階段完成：",
            "next_step": "下一步：",
        }
        lines = text.split("\n")
        current_key: str | None = None
        current_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            matched = False
            for key, heading in HEADINGS.items():
                if stripped.startswith(heading.rstrip("：")):
                    if current_key is not None:
                        sections[current_key] = "\n".join(current_lines).strip()
                    current_key = key
                    rest = stripped[len(heading.rstrip("：")):]
                    current_lines = [rest.lstrip("：").strip()] if rest.strip(":：").strip() else []
                    matched = True
                    break
            if not matched and current_key is not None:
                current_lines.append(line)
        if current_key is not None:
            sections[current_key] = "\n".join(current_lines).strip()
        return sections

    @pytest.mark.parametrize("stage", STAGES)
    def test_has_three_required_headings(self, stage: str) -> None:
        reply = format_genai_completed_feedback_reply(stage=stage, praise="你已經把感受說清楚了。")
        assert "你已經做到：" in reply
        assert "本階段完成：" in reply
        assert "下一步：" in reply

    @pytest.mark.parametrize("stage", STAGES)
    def test_contains_no_modification_language(self, stage: str) -> None:
        reply = format_genai_completed_feedback_reply(stage=stage, praise="你寫得很清楚。")
        forbidden = [
            "再補一句",
            "可以更具體",
            "再加入例子",
            "再想一想",
            "你可以再加強",
            "試著修改",
            "試著補一句",
        ]
        for phrase in forbidden:
            assert phrase not in reply, f"Found forbidden phrase '{phrase}' in stage {stage} reply"

    @pytest.mark.parametrize("stage", STAGES)
    def test_praise_section_is_non_empty(self, stage: str) -> None:
        reply = format_genai_completed_feedback_reply(stage=stage, praise="你已經把感受說清楚。")
        sections = self._parse_headings(reply)
        assert sections.get("praise"), f"Empty praise section for stage {stage}"

    def test_praise_trimmed_to_max_50_chars(self) -> None:
        long_praise = "a" * 60
        reply = format_genai_completed_feedback_reply(stage="R", praise=long_praise)
        sections = self._parse_headings(reply)
        # After trimming, the praise text in the section should be ≤ 50 chars (plus possible "…")
        praise_text = sections.get("praise", "")
        assert len(praise_text) <= 52, f"Praise too long: {len(praise_text)}"

    def test_fallback_praise_when_none(self) -> None:
        reply = format_genai_completed_feedback_reply(stage="O", praise=None)
        assert "你已經做到：" in reply
        assert reply.strip() != ""

    def test_does_not_contain_revision_headings(self) -> None:
        for stage in self.STAGES:
            reply = format_genai_completed_feedback_reply(stage=stage, praise="讚")
            assert "你可以再加強：" not in reply
            assert "再想一想：" not in reply
            assert "試著補一句：" not in reply


# ─────────────────────────────────────────────────────────────────────────────
# Control group isolation: format_control_feedback_reply stays as revision
# ─────────────────────────────────────────────────────────────────────────────

class TestControlFeedbackIsolation:
    """Control group formatter must not produce complete-card headings."""

    def test_control_reply_has_revision_headings(self) -> None:
        reply = format_control_feedback_reply(
            ok=False,
            missing=["還沒有寫出感受"],
            suggestions=["你看到這一幕有什麼感覺？"],
            stage="R",
            book_anchor="",
            example=None,
            praise="你有試著寫",
            student_draft="柿子很好吃",
        )
        assert "你已經做到：" in reply
        assert "你可以再加強：" in reply or "再想一想：" in reply
        # Must NOT have complete headings
        assert "本階段完成：" not in reply
        assert "下一步：" not in reply or "下一步" not in reply.split("本階段完成")[0]

    def test_control_reply_ok_true_does_not_use_complete_formatter(self) -> None:
        """Even when ok=True, control formatter must not produce 本階段完成 heading."""
        reply = format_control_feedback_reply(
            ok=True,
            missing=[],
            suggestions=[],
            stage="O",
            book_anchor="",
            example=None,
            praise="你寫得很好",
            student_draft="阿松爺爺把柿子送給大家",
        )
        assert "本階段完成：" not in reply


# ─────────────────────────────────────────────────────────────────────────────
# _looks_valid_feedback_narration
# ─────────────────────────────────────────────────────────────────────────────

class TestLooksValidFeedbackNarration:
    """Both complete and revision cards must be accepted; empty string must be rejected."""

    def setup_method(self) -> None:
        from app.routes.orid import _looks_valid_feedback_narration
        self._fn = _looks_valid_feedback_narration

    def test_complete_card_is_valid(self) -> None:
        complete = format_genai_completed_feedback_reply(stage="R", praise="你寫清楚了。")
        assert self._fn(complete)

    def test_revision_card_is_valid(self) -> None:
        revision = (
            "你已經做到：\n你有試著寫出感受。\n\n"
            "你可以再加強：\n補上原因會更好。\n\n"
            "試著補一句：\n我覺得＿＿＿，因為＿＿＿。"
        )
        assert self._fn(revision)

    def test_empty_is_invalid(self) -> None:
        assert not self._fn("")

    def test_missing_section_is_invalid(self) -> None:
        incomplete = "你已經做到：\n你有試著寫。"
        assert not self._fn(incomplete)


# ─────────────────────────────────────────────────────────────────────────────
# _apply_orid_rubric_ok_rule
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyOridRubricOkRule:
    """Level 3 or 4 always returns True regardless of initial ok; level 1/2 with strong missing returns False."""

    def setup_method(self) -> None:
        from app.routes.orid import _apply_orid_rubric_ok_rule
        self._fn = _apply_orid_rubric_ok_rule

    @pytest.mark.parametrize("stage", ["O", "R", "I", "D"])
    def test_level_3_returns_true(self, stage: str) -> None:
        rubric = {"rubric_focus": f"{stage}1", "rubric_level_estimate": {f"{stage}1": "3 達標"}}
        result = self._fn(False, rubric, ["一些缺口"], stage=stage)
        assert result is True

    @pytest.mark.parametrize("stage", ["O", "R", "I", "D"])
    def test_level_4_returns_true(self, stage: str) -> None:
        rubric = {"rubric_focus": f"{stage}1", "rubric_level_estimate": {f"{stage}1": "4 精進"}}
        result = self._fn(False, rubric, [], stage=stage)
        assert result is True

    def test_level_1_with_grounding_issue_stays_false(self) -> None:
        rubric = {"rubric_focus": "O1", "rubric_level_estimate": {"O1": "1 起步"}}
        result = self._fn(True, rubric, ["對齊教材：書裡沒有地瓜"], stage="O")
        assert result is False

    def test_level_2_stays_false(self) -> None:
        rubric = {"rubric_focus": "R1", "rubric_level_estimate": {"R1": "2 接近"}}
        result = self._fn(False, rubric, ["還沒有感受詞"], stage="R")
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# Frontend-side parser equivalence (pure Python implementation of TS logic)
# ─────────────────────────────────────────────────────────────────────────────

class TestFrontendParserEquivalence:
    """
    Simulates the TypeScript parseFeedbackNarration logic in Python to verify
    that the backend-generated messages parse into the expected kinds.
    """

    def _parse(self, text: str) -> dict | None:
        """Minimal Python replica of parseFeedbackNarration."""
        import re
        normalized = text.replace("\r\n", "\n").strip()
        if not normalized:
            return None

        def find_heading(pattern: str) -> tuple[int, int] | None:
            m = re.search(r"(?:^|\n)" + pattern, normalized, re.MULTILINE)
            if not m:
                return None
            return m.start(), m.start() + len(m.group(0))

        praise_h = find_heading(r"你已經做到[:：]?\s*")
        if not praise_h:
            return None

        # Try complete card
        complete_h = find_heading(r"本階段完成[:：]?\s*")
        if complete_h and complete_h[0] > praise_h[0]:
            next_h = find_heading(r"下一步[:：]?\s*")
            praise_text = normalized[praise_h[1]:complete_h[0]].strip()
            completion_text = normalized[complete_h[1]:next_h[0] if next_h else len(normalized)].strip()
            next_text = normalized[next_h[1]:].strip() if next_h else None
            if praise_text and completion_text:
                return {"kind": "complete", "praise": praise_text, "completion": completion_text, "nextStep": next_text}

        # Try revision card
        rethink_h = find_heading(r"你可以再加強[:：]?\s*") or find_heading(r"再想一想[:：]?\s*")
        example_h = (
            find_heading(r"(?:試著補一句|試試看(?:這樣寫)?)[:：]?\s*")
            or find_heading(r"可以這樣修改[:：]?\s*")
        )
        if not rethink_h or not example_h:
            return None
        if not (praise_h[0] < rethink_h[0] < example_h[0]):
            return None
        praise = normalized[praise_h[1]:rethink_h[0]].strip()
        rethink = normalized[rethink_h[1]:example_h[0]].strip()
        example = normalized[example_h[1]:].strip()
        if not praise or not rethink:
            return None
        return {"kind": "revision", "praise": praise, "rethink": rethink, "example": example or None}

    @pytest.mark.parametrize("stage", ["O", "R", "I", "D"])
    def test_genai_complete_reply_parses_as_complete(self, stage: str) -> None:
        reply = format_genai_completed_feedback_reply(stage=stage, praise="你已經把感受說清楚了。")
        parsed = self._parse(reply)
        assert parsed is not None, f"Parse failed for stage {stage}"
        assert parsed["kind"] == "complete"
        assert parsed["praise"]
        assert parsed["completion"]
        assert parsed.get("nextStep")

    def test_revision_reply_parses_as_revision(self) -> None:
        revision = (
            "你已經做到：\n你有試著寫出感受。\n\n"
            "你可以再加強：\n補上原因會更好。\n\n"
            "試著補一句：\n我覺得＿＿＿，因為＿＿＿。"
        )
        parsed = self._parse(revision)
        assert parsed is not None
        assert parsed["kind"] == "revision"

    def test_old_three_section_still_parses(self) -> None:
        """Old chat history with 三段式 should still parse as revision (backward compat)."""
        old_msg = (
            "你已經做到：\n你有把情節寫出來。\n\n"
            "再想一想：\n你的感受是什麼？\n\n"
            "試試看這樣寫：\n我覺得＿＿，因為＿＿。"
        )
        parsed = self._parse(old_msg)
        assert parsed is not None
        assert parsed["kind"] == "revision"

    def test_complete_card_has_no_modification_fields(self) -> None:
        reply = format_genai_completed_feedback_reply(stage="I", praise="你想法很好。")
        parsed = self._parse(reply)
        assert parsed is not None
        assert parsed["kind"] == "complete"
        # Complete cards must not contain rethink/example fields
        assert "rethink" not in parsed
        assert "example" not in parsed or parsed.get("example") is None

    def test_empty_text_returns_none(self) -> None:
        assert self._parse("") is None

    def test_text_without_headings_returns_none(self) -> None:
        assert self._parse("學生寫得很好！繼續加油。") is None


# ─────────────────────────────────────────────────────────────────────────────
# ORID_REQUIRED_PASS default unchanged
# ─────────────────────────────────────────────────────────────────────────────

class TestOridRequiredPassDefaultUnchanged:
    """Global ORID_REQUIRED_PASS default must remain at 2 (not 1)."""

    def test_default_is_two(self) -> None:
        import importlib
        # Import fresh to avoid cached env overrides
        import app.routes.orid as orid_module
        assert orid_module.ORID_REQUIRED_PASS_DEFAULT == 2


# ─────────────────────────────────────────────────────────────────────────────
# Research snapshot presence (unit-level check on the formatter)
# ─────────────────────────────────────────────────────────────────────────────

class TestResearchSnapshotContent:
    """
    Verifies that format_genai_completed_feedback_reply does NOT include
    modification content (the research snapshot is never exposed to the student).
    """

    def test_completion_message_does_not_leak_research_missing(self) -> None:
        reply = format_genai_completed_feedback_reply(
            stage="R",
            praise="你有寫感受了。",
        )
        # The formatter doesn't receive research_missing, but guard anyway
        assert "missing" not in reply.lower()
        assert "suggestions" not in reply.lower()
