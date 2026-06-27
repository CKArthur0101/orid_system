"""Tests for orid_badges service."""
from __future__ import annotations

import pytest
from app.services.orid_badges import (
    BADGE_ORDER,
    _score_from_writing_obj,
    calculate_earned_badges,
    get_new_badges,
    should_show_badge_modal,
)


class TestCalculateEarnedBadges:
    def test_no_content_no_badges(self):
        result = calculate_earned_badges(
            has_writing_content=False,
            has_used_feedback_or_prompt=False,
            total_score=None,
        )
        assert result == []

    def test_content_plus_prompt_gives_start(self):
        result = calculate_earned_badges(
            has_writing_content=True,
            has_used_feedback_or_prompt=True,
            total_score=None,
        )
        assert "badge_start" in result

    def test_content_without_prompt_no_start(self):
        result = calculate_earned_badges(
            has_writing_content=True,
            has_used_feedback_or_prompt=False,
            total_score=None,
        )
        assert "badge_start" not in result

    def test_score_30_gives_bronze(self):
        result = calculate_earned_badges(
            has_writing_content=True,
            has_used_feedback_or_prompt=True,
            total_score=30,
        )
        assert "badge_30" in result
        assert "badge_60" not in result

    def test_score_90_gives_all_score_badges(self):
        result = calculate_earned_badges(
            has_writing_content=True,
            has_used_feedback_or_prompt=True,
            total_score=90,
        )
        assert "badge_30" in result
        assert "badge_60" in result
        assert "badge_90" in result

    def test_badges_not_earned_for_score_below_threshold(self):
        result = calculate_earned_badges(
            has_writing_content=False,
            has_used_feedback_or_prompt=False,
            total_score=29,
        )
        assert "badge_30" not in result


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


def test_badge_order_covers_all_four():
    assert len(BADGE_ORDER) == 4
    assert "badge_start" in BADGE_ORDER
    assert "badge_90" in BADGE_ORDER


class TestScoreFromWritingObj:
    def test_persisted_score_snapshot(self):
        obj = {"score": {"totalScore": 12, "maxTotal": 90}}
        snap, total = _score_from_writing_obj(obj)
        assert total == 12
        assert snap["totalScore"] == 12

    def test_compute_from_feedback_meta(self):
        obj = {
            "stages": {
                "O": {
                    "feedback": {
                        "d1": {"meta": {"rubric_level_estimate": "2 接近", "rubric_focus": "O1"}}
                    }
                }
            }
        }
        snap, total = _score_from_writing_obj(obj)
        assert total == 5
        assert snap["totalScore"] == 5
