"""Control-group check: checklist ticks, same pass bar, no draft quotation."""
from app.services.action_pass import experimental_action_override
from app.services.control_check import (
    check_control_stage,
    check_control_synthesis,
    is_unfilled_scaffold,
    silent_stage_checks,
    silent_synthesis_checks,
)


def test_silent_stage_check_is_one_line_for_the_whole_stage():
    failed = silent_stage_checks("R", False)
    assert len(failed) == 1
    assert failed[0].passed is False
    assert "因為" not in failed[0].label

    passed = silent_stage_checks("R", True)
    assert passed[0].passed is True
    assert passed[0].label == failed[0].label


def test_silent_synthesis_checks_follow_level_three():
    checks = silent_synthesis_checks(
        {
            "content_integration": 3,
            "coherence": 2,
            "reflection_depth": 4,
            "action_application": 1,
        }
    )
    assert [item.passed for item in checks] == [True, False, True, False]


def test_unfilled_sentence_frame_is_not_student_writing():
    text = "我覺得＿＿，因為＿＿。"
    assert is_unfilled_scaffold(text)
    result = check_control_stage(stage="R", text=text, week=1, stages_already_passed=set())
    assert result.ok is False
    assert result.reply == ""
    assert result.checks
    assert not any(item.passed for item in result.checks)
    assert "我覺得＿＿" not in result.reply


def test_observation_needs_an_event_not_only_a_feeling():
    result = check_control_stage(
        stage="O",
        text="我覺得很溫暖，因為很感人。",
        week=1,
        stages_already_passed=set(),
    )
    assert result.ok is False
    assert result.reply == ""
    assert result.checks[0].passed is False
    assert "？" not in result.reply


def test_observation_passes_without_quoting_the_draft():
    draft = "一開始阿松爺爺把柿子藏起來，後來沒有分給松鼠一起吃。"
    result = check_control_stage(stage="O", text=draft, week=1, stages_already_passed=set())
    assert result.ok is True
    assert result.reply == "這段可以了。"
    assert all(item.passed for item in result.checks)
    assert "藍籃子" not in result.reply
    assert "柿子" not in result.reply
    assert "？" not in result.reply


def test_feeling_needs_a_reason():
    missing = check_control_stage(stage="R", text="我覺得很難過。", week=1, stages_already_passed={"O"})
    assert missing.ok is False
    assert missing.checks[0].passed is True
    assert missing.checks[1].passed is False

    passed = check_control_stage(
        stage="R",
        text="我覺得很難過，因為爺爺把柿子藏起來。",
        week=1,
        stages_already_passed={"O"},
    )
    assert passed.ok is True
    assert passed.reply == "這段可以了。"


def test_insight_and_action_use_the_same_bar():
    insight = check_control_stage(
        stage="I",
        text="我明白分享很重要，因為大家一起吃才開心。",
        week=2,
        stages_already_passed={"O", "R"},
    )
    assert insight.ok is True
    assert insight.reply == "這段可以了。"

    wish = check_control_stage(stage="D", text="我要變成更好的人。", week=2, stages_already_passed=set())
    assert wish.ok is False

    action = check_control_stage(
        stage="D",
        text="下次同學忘了帶筆的時候，我會先把一支筆借給他。",
        week=2,
        stages_already_passed={"O", "R", "I"},
    )
    assert action.ok is True
    assert action.reply == "這段可以了。"


def test_vague_action_does_not_pass_even_with_a_person():
    result = check_control_stage(
        stage="D",
        text="以後如果遇到家人需要幫忙，我會多主動一點。",
        week=4,
        stages_already_passed=set(),
        book_pack={"d_action_markers": ["家人", "家事", "碗"]},
    )
    assert result.ok is False
    assert result.checks[0].label == "我有寫我要做的那一步"
    assert result.checks[0].passed is False
    assert "？" not in result.reply


def test_concrete_family_action_passes_without_a_fixed_sentence():
    result = check_control_stage(
        stage="D",
        text="晚上我把碗收進水槽，再請爸爸洗碗。",
        week=4,
        stages_already_passed={"O", "R", "I"},
        book_pack={"d_action_markers": ["家人", "家事", "碗", "收"]},
    )
    assert result.ok is True
    assert result.reply == "這段可以了。"
    assert "？" not in result.reply


def test_off_book_action_does_not_pass():
    result = check_control_stage(
        stage="D",
        text="每天放學後，我會把故事寫下來。",
        week=4,
        stages_already_passed=set(),
        book_pack={"d_action_markers": ["家人", "家事", "碗"]},
    )
    assert result.ok is False
    assert result.checks[-1].label == "我有連到這本書的事情"
    assert result.checks[-1].passed is False
    assert "？" not in result.reply


def test_synthesis_passes_only_when_four_parts_are_present():
    draft = (
        "一開始阿松爺爺把柿子藏起來，後來沒有分給松鼠。"
        "我覺得很難過，因為他沒有和大家一起吃。"
        "我明白分享很重要，所以我想把這個道理記得。"
        "下次同學忘了帶點心，我會先把我的點心分給他。"
    )
    result = check_control_synthesis(text=draft)
    assert result.ok is True
    assert result.levels is not None
    assert all(level >= 3 for level in result.levels.values())
    assert result.reply == "這篇可以了。"
    assert all(item.passed for item in result.checks)
    assert "柿子" not in result.reply
    assert "？" not in result.reply


def test_experimental_false_pass_is_held_to_the_same_action_bar():
    ok, missing, suggestions, meta = experimental_action_override(
        stage="D",
        student_text="以後如果遇到家人需要幫忙，我會多主動一點。",
        book_pack={
            "book_title": "朱家故事",
            "d_action_student_theme": "一起分擔家事、體諒家人",
            "d_action_question": "讀完《朱家故事》，你可以為家人主動做哪一件事？",
            "d_action_markers": ["家人", "家事", "碗"],
        },
        ok=True,
        missing=[],
        suggestions=[],
        rubric_meta={"rubric_level_estimate": {"D1": "3 達標"}},
        keep_model_sentences=True,
    )
    assert ok is False
    assert meta["rubric_level_estimate"]["D1"] == "2 接近"
    assert missing and "？" not in missing[0]
    assert suggestions and suggestions[0].endswith("？")


def test_synthesis_shows_one_gap_and_scores_each_part():
    draft = "一開始阿松爺爺把柿子藏起來，後來沒有分給松鼠。我覺得很難過。"
    result = check_control_synthesis(text=draft)
    assert result.ok is False
    assert result.levels is not None
    assert result.levels["content_integration"] >= 3
    assert result.levels["action_application"] < 3
    assert result.reply == ""
    assert result.checks[0].passed is True
    assert any(not item.passed for item in result.checks)
    assert "？" not in result.reply
