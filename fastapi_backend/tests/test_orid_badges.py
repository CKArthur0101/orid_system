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
    ensure_synthesis_mismatch_reply,
    synthesis_fallback_reply,
    synthesis_visible_reply,
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

    def test_visible_reply_keeps_model_sentences_and_falls_back_only_when_empty(self):
        fail_reply = (
            "你已經做到：\n你寫到阿松爺爺不分享柿子。\n"
            "再想一想：\n還可以補一件事。\n可以這樣修改：\n他給了什麼？"
        )
        assert synthesis_visible_reply(fail_reply, "content_integration") == fail_reply
        fallback = synthesis_visible_reply("  ", "content_integration")
        assert fallback == synthesis_fallback_reply("content_integration")
        assert "你有把故事和自己的想法放進整合稿" not in fallback

    def test_passed_synthesis_reply_affirms_without_questions(self):
        model_reply = (
            "你已經做到：\n"
            "你寫到柿子很甜、阿松爺爺只把柿子蒂給哎喲奶奶，也說出自己覺得他小氣。"
            "你覺得這個畫面有把阿松爺爺的做法寫清楚嗎？\n"
            "再想一想：\n"
            "你從他不分享想到自己也不會比較開心，接著寫出借彩色筆。"
            "故事和行動之間的關係，讀起來清楚嗎？\n"
            "可以這樣修改：\n"
            "你的文章已經有故事、自己的體會和做得到的行動，不需要特別修改。"
            "你可以保留這個版本完成整合短文嗎？"
        )
        reply = synthesis_visible_reply(model_reply, None)
        assert "你寫到柿子很甜、阿松爺爺只把柿子蒂給哎喲奶奶" in reply
        assert "借彩色筆" in reply
        assert "本階段完成：" in reply
        assert "不需要特別修改" in reply
        assert "下一步：" in reply
        assert "可以保留現在的內容並儲存作品。" in reply
        assert "再想一想：" not in reply
        assert "可以這樣修改：" not in reply
        assert "？" not in reply
        assert "?" not in reply

    def test_mismatch_reply_names_the_student_sentence(self):
        reply = ensure_synthesis_mismatch_reply(
            "你已經做到：\n你寫到阿松爺爺把葡萄分給全班。\n再想一想：\n可以多說分享。\n可以這樣修改：\n哪個地方讓你覺得分享很好？",
            "阿松爺爺把葡萄分給全班",
        )
        assert "你寫到阿松爺爺把葡萄分給全班" in reply
        assert "跟故事裡發生的不太一樣喔" in reply
        assert "哪個地方讓你覺得分享很好" not in reply

    def test_mismatch_reply_keeps_model_wording_when_it_already_says_so(self):
        model = (
            "你已經做到：\n你有寫到想把便當分給同學。\n"
            "再想一想：\n阿松爺爺把葡萄分給全班，這件事故事裡沒有發生。\n"
            "可以這樣修改：\n你還記得故事裡大家後來一起做了什麼嗎？用你自己的話說說看。"
        )
        reply = ensure_synthesis_mismatch_reply(model, "阿松爺爺把葡萄分給全班")
        assert reply == model
        assert "跟故事裡發生的不太一樣喔" not in reply
