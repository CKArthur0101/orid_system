from app.routes.teacher import _teacher_display_stage


def test_display_stage_raises_with_draft_even_if_coach_stuck_on_o() -> None:
    assert (
        _teacher_display_stage(interaction_count=5, coach_stage="O", writing_completed_stages=4) == "D"
    )


def test_no_interaction_always_not_started() -> None:
    assert (
        _teacher_display_stage(interaction_count=0, coach_stage="D", writing_completed_stages=4)
        == "NOT_STARTED"
    )


def test_merges_max_of_coach_and_draft_counts() -> None:
    assert _teacher_display_stage(interaction_count=2, coach_stage="O", writing_completed_stages=2) == "R"


def test_unknown_coach_stage_treated_as_not_started_then_o_when_active() -> None:
    assert _teacher_display_stage(interaction_count=1, coach_stage="X", writing_completed_stages=0) == "O"
