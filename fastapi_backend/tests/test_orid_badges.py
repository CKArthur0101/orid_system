"""Tests for orid_badges service."""
from __future__ import annotations

from app.services.orid_badges import (
    BADGE_ORDER,
    calculate_earned_badges,
    calculate_earned_synthesis_badges,
    get_new_badges,
    should_show_badge_modal,
    stages_passed_from_orid_levels,
    stages_passed_from_writing_obj,
)
from app.content.synthesis_rubric import (
    first_synthesis_gap,
    lock_synthesis_content_for_grounding,
    synthesis_fallback_reply,
)


class TestCalculateEarnedBadges:
    def test_no_content_no_badges(self):
        result = calculate_earned_badges(
            has_writing_content=False,
            has_used_feedback_or_prompt=False,
            stages_passed=None,
        )
        assert result == []

    def test_content_plus_prompt_gives_start(self):
        result = calculate_earned_badges(
            has_writing_content=True,
            has_used_feedback_or_prompt=True,
            stages_passed=None,
        )
        assert "badge_start" in result

    def test_content_without_prompt_no_start(self):
        result = calculate_earned_badges(
            has_writing_content=True,
            has_used_feedback_or_prompt=False,
            stages_passed=None,
        )
        assert "badge_start" not in result

    def test_o_passed_gives_bronze(self):
        result = calculate_earned_badges(
            has_writing_content=True,
            has_used_feedback_or_prompt=True,
            stages_passed=["O"],
        )
        assert "badge_30" in result
        assert "badge_60" not in result

    def test_ori_passed_gives_silver(self):
        result = calculate_earned_badges(
            has_writing_content=True,
            has_used_feedback_or_prompt=True,
            stages_passed=["O", "R", "I"],
        )
        assert "badge_30" in result
        assert "badge_60" in result
        assert "badge_90" not in result

    def test_all_stages_gives_gold(self):
        result = calculate_earned_badges(
            has_writing_content=True,
            has_used_feedback_or_prompt=True,
            stages_passed=["O", "R", "I", "D"],
        )
        assert "badge_30" in result
        assert "badge_60" in result
        assert "badge_90" in result


class TestStagesPassedHelpers:
    def test_from_writing_ok(self):
        obj = {
            "stages": {
                "O": {"feedback": {"d1": {"ok": True}}},
                "R": {"feedback": {"d1": {"ok": False}}},
                "I": {"d1": "text"},
            }
        }
        assert stages_passed_from_writing_obj(obj, mode="ok") == {"O"}

    def test_from_writing_content(self):
        obj = {
            "stages": {
                "O": {"d1": "事實"},
                "R": {"d1": "", "d2": "  "},
                "I": {"d2": "想法"},
            }
        }
        assert stages_passed_from_writing_obj(obj, mode="content") == {"O", "I"}

    def test_from_orid_levels(self):
        assert stages_passed_from_orid_levels({"O1": 3, "R1": 2, "I1": 4}) == {"O", "I"}


class TestGetNewBadges:
    def test_all_new(self):
        new = get_new_badges([], ["badge_start", "badge_30"])
        assert set(new) == {"badge_start", "badge_30"}

    def test_some_already_earned(self):
        new = get_new_badges(["badge_start"], ["badge_start", "badge_30"])
        assert new == ["badge_30"]

    def test_no_new(self):
        new = get_new_badges(["badge_start"], ["badge_start"])
        assert new == []


class TestShouldShowBadgeModal:
    def test_true_when_new_badges(self):
        assert should_show_badge_modal(["badge_start"]) is True

    def test_false_when_empty(self):
        assert should_show_badge_modal([]) is False


def test_badge_order_covers_orid_track_plus_synthesis():
    assert len(BADGE_ORDER) == 8
    assert "badge_start" in BADGE_ORDER
    assert "badge_90" in BADGE_ORDER
    assert "badge_synthesis_content" in BADGE_ORDER
    assert "badge_synthesis_action" in BADGE_ORDER


class TestCalculateEarnedSynthesisBadge:
    def test_missing_levels_give_no_badges(self):
        assert calculate_earned_synthesis_badges(rubric_levels={}) == []

    def test_only_level_three_or_four_earn_matching_badges(self):
        result = calculate_earned_synthesis_badges(
            rubric_levels={
                "content_integration": 3,
                "coherence": 2,
                "reflection_depth": "4 精進",
                "action_application": 1,
            }
        )
        assert result == ["badge_synthesis_content", "badge_synthesis_reflection"]

    def test_all_four_criteria_can_earn_four_badges(self):
        result = calculate_earned_synthesis_badges(
            rubric_levels={
                "content_integration": 3,
                "coherence": 3,
                "reflection_depth": 3,
                "action_application": 3,
            }
        )
        assert result == [
            "badge_synthesis_content",
            "badge_synthesis_coherence",
            "badge_synthesis_reflection",
            "badge_synthesis_action",
        ]

    def test_independent_from_orid_stage_badges(self):
        """The synthesis badge must not imply/require any O/R/I/D stage badge."""
        synth = calculate_earned_synthesis_badges(
            rubric_levels={"content_integration": 3}
        )
        orid = calculate_earned_badges(
            has_writing_content=False,
            has_used_feedback_or_prompt=False,
            stages_passed=None,
        )
        assert synth == ["badge_synthesis_content"]
        assert orid == []

    def test_first_gap_and_fallback_guidance_target_same_criterion(self):
        levels = {
            "content_integration": 3,
            "coherence": 3,
            "reflection_depth": 2,
            "action_application": 1,
        }
        focus = first_synthesis_gap(levels)
        assert focus == "reflection_depth"
        reply = synthesis_fallback_reply(focus)
        assert "為什麼" in reply
        assert "下一次遇到" not in reply

    def test_material_grounding_issue_caps_content_and_blocks_its_badge(self):
        levels = lock_synthesis_content_for_grounding(
            {
                "content_integration": 4,
                "coherence": 4,
                "reflection_depth": 4,
                "action_application": 4,
            }
        )

        assert levels["content_integration"] == 2
        assert first_synthesis_gap(levels) == "content_integration"
        assert "badge_synthesis_content" not in calculate_earned_synthesis_badges(
            rubric_levels=levels
        )
