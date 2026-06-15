import json

from app.routes.teacher import _extract_submission_research_fields, _teacher_display_stage


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


def test_extract_submission_research_fields_exports_text_and_rubric_meta() -> None:
    content = json.dumps(
        {
            "schema": "orid_writing_v1",
            "stages": {
                "O": {
                    "d1": "阿松爺爺一開始不分享柿子。",
                    "feedback": {
                        "d1": {
                            "ok": True,
                            "meta": {
                                "rubric_focus": "O1",
                                "rubric_level_estimate": "3 達標",
                            },
                        }
                    },
                },
                "R": {"d1": "我覺得難過。"},
            },
        },
        ensure_ascii=False,
    )

    fields = _extract_submission_research_fields(content)

    assert fields["O_text"] == "阿松爺爺一開始不分享柿子。"
    assert fields["O_feedback_ok"] == "true"
    assert fields["O_rubric_focus"] == "O1"
    assert fields["O_rubric_level_estimate"] == "3 達標"
    assert fields["R_text"] == "我覺得難過。"
    assert fields["R_feedback_ok"] == ""
