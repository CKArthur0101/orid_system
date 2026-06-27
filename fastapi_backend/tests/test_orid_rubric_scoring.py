"""Tests for orid_rubric_scoring service."""
from __future__ import annotations

import pytest
from app.services.orid_rubric_scoring import (
    TOTAL_MAX,
    apply_single_level_estimate,
    calculate_orid_sel_score,
    clamp_total_score,
    collect_levels_from_writing_obj,
    extract_orid_levels_from_rubric_meta,
    parse_level,
    score_criterion,
)


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


class TestScoreCriterion:
    def test_level1(self):
        assert score_criterion(1) == pytest.approx(2.5)

    def test_level4(self):
        assert score_criterion(4) == pytest.approx(10.0)

    def test_none_gives_zero(self):
        assert score_criterion(None) == 0.0


class TestClampTotalScore:
    def test_normal(self):
        assert clamp_total_score(55.5) == 56

    def test_above_max(self):
        assert clamp_total_score(100) == TOTAL_MAX

    def test_below_zero(self):
        assert clamp_total_score(-5) == 0

    def test_exact_max(self):
        assert clamp_total_score(90) == 90


class TestCalculateOridSelScore:
    def test_all_level4_gives_90(self):
        orid = {"O1": 4, "R1": 4, "I1": 4, "D1": 4}
        sel = {"SEL_EA": 4, "SEL_PT_R": 4, "SEL_VR": 4, "SEL_PT_I": 4, "SEL_RA": 4}
        result = calculate_orid_sel_score(orid, sel)
        assert result["totalScore"] == 90
        assert result["oridSubtotal"] == pytest.approx(40.0)
        assert result["selSubtotal"] == pytest.approx(50.0)
        assert result["missing"] == []

    def test_all_level1_gives_minimum(self):
        orid = {"O1": 1, "R1": 1, "I1": 1, "D1": 1}
        sel = {"SEL_EA": 1, "SEL_PT_R": 1, "SEL_VR": 1, "SEL_PT_I": 1, "SEL_RA": 1}
        result = calculate_orid_sel_score(orid, sel)
        # 4 * 2.5 + 5 * 2.5 = 10 + 12.5 = 22.5 → rounded to 23
        assert result["totalScore"] == 23
        assert result["oridSubtotal"] == pytest.approx(10.0)
        assert result["selSubtotal"] == pytest.approx(12.5)

    def test_missing_criteria_reported(self):
        result = calculate_orid_sel_score({}, {})
        assert "O1" in result["missing"]
        assert "SEL_EA" in result["missing"]
        assert result["totalScore"] == 0

    def test_partial_scores(self):
        orid = {"O1": 3, "R1": 2}  # I1, D1 missing
        sel = {"SEL_EA": 3, "SEL_VR": 4}
        result = calculate_orid_sel_score(orid, sel)
        # ORID: 7.5 + 5 + 0 + 0 = 12.5
        # SEL: 7.5 + 0 + 10 + 0 + 0 = 17.5
        # Total: 30.0
        assert result["totalScore"] == 30
        assert "I1" in result["missing"]
        assert "D1" in result["missing"]

    def test_score_never_exceeds_90(self):
        orid = {"O1": 4, "R1": 4, "I1": 4, "D1": 4}
        sel = {"SEL_EA": 4, "SEL_PT_R": 4, "SEL_VR": 4, "SEL_PT_I": 4, "SEL_RA": 4}
        result = calculate_orid_sel_score(orid, sel)
        assert result["totalScore"] <= 90


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
        result = calculate_orid_sel_score(orid, sel)
        assert result["totalScore"] == 5

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
        assert calculate_orid_sel_score(orid, sel)["totalScore"] == 8

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
        assert calculate_orid_sel_score(orid, sel)["totalScore"] == 13
