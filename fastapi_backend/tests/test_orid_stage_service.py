from app.services.orid_stage import build_stage_history, decide_stage_progress, resolve_stage_thresholds


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
    assert out.next_stuck_rounds == 0


def test_resolve_stage_thresholds_guided_relaxes_pass_after_stuck_threshold():
    out = resolve_stage_thresholds(
        required_pass=3,
        min_ai_turns_same_stage=2,
        progression_mode="guided",
        stuck_rounds=4,
        guided_stuck_threshold=4,
        guided_pass_relax=1,
        guided_min_pass=1,
    )
    assert out.required_pass == 2
    assert out.min_ai_turns_same_stage == 2


def test_resolve_stage_thresholds_strict_never_relaxes():
    out = resolve_stage_thresholds(
        required_pass=3,
        min_ai_turns_same_stage=2,
        progression_mode="strict",
        stuck_rounds=10,
        guided_stuck_threshold=4,
        guided_pass_relax=1,
        guided_min_pass=1,
    )
    assert out.required_pass == 3
    assert out.min_ai_turns_same_stage == 2

