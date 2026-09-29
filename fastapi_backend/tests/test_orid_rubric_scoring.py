"""Tests for orid_rubric_scoring service."""
from __future__ import annotations

from app.services.orid_rubric_scoring import (
    apply_single_level_estimate,
    collect_levels_from_writing_obj,
    extract_orid_levels_from_rubric_meta,
    parse_level,
    primary_orid_level_from_rubric_meta,
)
from app.content.rubrics import (
    WEEK1_ORID_RUBRIC,
    WEEK1_SEL_RUBRIC,
    WEEK3_ORID_RUBRIC,
    WEEK3_SEL_RUBRIC,
    WEEK5_ORID_RUBRIC,
    WEEK5_SEL_RUBRIC,
)


def test_rubrics_do_not_define_ai_numeric_scoring():
    for rubric in (
        WEEK1_ORID_RUBRIC,
        WEEK1_SEL_RUBRIC,
        WEEK3_ORID_RUBRIC,
        WEEK3_SEL_RUBRIC,
        WEEK5_ORID_RUBRIC,
        WEEK5_SEL_RUBRIC,
    ):
        assert "scoring_formula" not in rubric
        assert "scoring_note" not in rubric
        assert "total_score" not in rubric


def test_all_books_share_identical_orid_and_sel_standards():
    assert WEEK1_ORID_RUBRIC == WEEK3_ORID_RUBRIC == WEEK5_ORID_RUBRIC
    assert WEEK1_SEL_RUBRIC == WEEK3_SEL_RUBRIC == WEEK5_SEL_RUBRIC

    # Separate objects prevent a book-specific runtime mutation from leaking.
    assert WEEK1_ORID_RUBRIC is not WEEK3_ORID_RUBRIC
    assert WEEK3_ORID_RUBRIC is not WEEK5_ORID_RUBRIC
    assert WEEK1_SEL_RUBRIC is not WEEK3_SEL_RUBRIC
    assert WEEK3_SEL_RUBRIC is not WEEK5_SEL_RUBRIC


def test_unified_d_level_three_requires_action_and_story_alignment():
    level_three = WEEK1_ORID_RUBRIC["by_stage"]["D"][0]["levels"][2]["desc"]
    assert "具體可行" in level_three
    assert "呼應故事體會" in level_three


class TestParseLevel:
    def test_int(self):
        assert parse_level(3) == 3

    def test_int_string(self):
        assert parse_level("2") == 2

    def test_labelled_string(self):
        assert parse_level("3 達標") == 3

    def test_chinese_only(self):
        assert parse_level("精進") == 4

    def test_none_returns_none(self):
        assert parse_level(None) is None

    def test_out_of_range_returns_none(self):
        assert parse_level(5) is None
        assert parse_level(0) is None

    def test_garbage_returns_none(self):
        assert parse_level("abc") is None


class TestExtractOridLevels:
    def test_short_keys(self):
        meta = {"O": 3, "R": 2, "I": 4, "D": 1}
        result = extract_orid_levels_from_rubric_meta(meta)
        assert result == {"O1": 3, "R1": 2, "I1": 4, "D1": 1}

    def test_long_keys(self):
        meta = {"O1": "3 達標", "R1": 2}
        result = extract_orid_levels_from_rubric_meta(meta)
        assert result["O1"] == "3 達標"
        assert result["R1"] == 2

    def test_empty_meta(self):
        assert extract_orid_levels_from_rubric_meta({}) == {}

    def test_string_json_meta(self):
        meta = '{"O": 3, "R": 2}'
        result = extract_orid_levels_from_rubric_meta(meta)
        assert result == {"O1": 3, "R1": 2}

    def test_plain_string_meta_no_crash(self):
        assert extract_orid_levels_from_rubric_meta("not a dict") == {}


class TestApplySingleLevelEstimate:
    def test_plain_string_o_stage(self):
        orid: dict = {}
        sel: dict = {}
        apply_single_level_estimate(
            stage="O",
            rubric_focus="O1",
            rubric_level_estimate="2 接近",
            orid_levels=orid,
            sel_levels=sel,
        )
        assert orid == {"O1": 2}

    def test_plain_string_without_focus_uses_stage(self):
        orid: dict = {}
        sel: dict = {}
        apply_single_level_estimate(
            stage="R",
            rubric_focus=None,
            rubric_level_estimate="3 達標",
            orid_levels=orid,
            sel_levels=sel,
        )
        assert orid == {"R1": 3}

    def test_collect_from_writing_obj(self):
        writing = {
            "schema": "orid_writing_v1",
            "week": 1,
            "stages": {
                "O": {
                    "d1": "text",
                    "feedback": {
                        "d1": {
                            "meta": {
                                "rubric_focus": "O1",
                                "rubric_level_estimate": "2 接近",
                            }
                        }
                    },
                },
                "R": {
                    "d1": "text",
                    "feedback": {
                        "d1": {
                            "rubric_focus": "R1",
                            "rubric_level_estimate": "3 達標",
                        }
                    },
                },
            },
        }
        orid, sel = collect_levels_from_writing_obj(writing)
        assert orid == {"O1": 2, "R1": 3}
        assert sel == {}


def test_primary_orid_level_from_rubric_meta_dict():
    meta = {"rubric_focus": "O1", "rubric_level_estimate": {"O1": "2 接近", "SEL_EA": "3 達標"}}
    assert primary_orid_level_from_rubric_meta(meta, stage="O") == 2
