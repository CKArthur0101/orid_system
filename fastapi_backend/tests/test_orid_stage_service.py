from app.services.orid_stage import build_stage_history, decide_stage_progress


class _Msg:
    def __init__(self, stage: str, sender: str, text: str):
        self.stage = stage
        self.sender = sender
        self.text = text


def test_build_stage_history_filters_by_stage():
    msgs = [
        _Msg("O", "student", "o1"),
        _Msg("R", "student", "r1"),
        _Msg("O", "ai", "o2"),
    ]
    out = build_stage_history(msgs, current_stage="O", history_limit=10)
    assert out == [
        {"role": "user", "content": "o1"},
        {"role": "assistant", "content": "o2"},
    ]


def test_decide_stage_progress_advances_when_thresholds_met():
    out = decide_stage_progress(
        current_stage="O",
        stage_turn=1,
        required_pass=2,
        pass_ok=True,
        ai_count_same_stage=2,
        min_ai_turns_same_stage=2,
        next_stage_func=lambda _: "R",
    )
    assert out.will_advance is True
    assert out.next_stage == "R"
    assert out.next_stage_turn == 0

