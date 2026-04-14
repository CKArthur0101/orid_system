from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StageThresholds:
    required_pass: int
    min_ai_turns_same_stage: int


@dataclass
class StageProgressDecision:
    pass_ok: bool
    reason: str | None
    will_advance: bool
    next_stage: str
    next_stage_turn: int
    next_stuck_rounds: int
    effective_required_pass: int
    effective_min_ai_turns_same_stage: int


def build_stage_history(
    messages: list[Any],
    *,
    current_stage: str,
    history_limit: int,
) -> list[dict[str, str]]:
    filtered = [m for m in messages if (getattr(m, "stage", "") or "").strip().upper() == current_stage]
    out: list[dict[str, str]] = []
    for m in filtered[-history_limit:]:
        role = "user" if getattr(m, "sender", "") == "student" else "assistant"
        out.append({"role": role, "content": str(getattr(m, "text", "") or "")})
    return out


def decide_stage_progress(
    *,
    current_stage: str,
    stage_turn: int,
    required_pass: int,
    pass_ok: bool,
    ai_count_same_stage: int,
    min_ai_turns_same_stage: int,
    next_stage_func,
    progression_mode: str = "guided",
    stuck_rounds: int = 0,
    guided_stuck_threshold: int = 4,
    guided_pass_relax: int = 1,
    guided_min_pass: int = 1,
    guided_relax_min_turns: int = 0,
) -> StageProgressDecision:
    thresholds = resolve_stage_thresholds(
        required_pass=required_pass,
        min_ai_turns_same_stage=min_ai_turns_same_stage,
        progression_mode=progression_mode,
        stuck_rounds=stuck_rounds,
        guided_stuck_threshold=guided_stuck_threshold,
        guided_pass_relax=guided_pass_relax,
        guided_min_pass=guided_min_pass,
        guided_relax_min_turns=guided_relax_min_turns,
    )
    stage = (current_stage or "O").strip().upper()
    new_turn = stage_turn + 1 if pass_ok else stage_turn
    will_advance = (
        pass_ok
        and stage != "D"
        and new_turn >= thresholds.required_pass
        and ai_count_same_stage >= thresholds.min_ai_turns_same_stage
    )
    next_stuck = 0 if pass_ok else max(stuck_rounds, 0) + 1
    if will_advance:
        return StageProgressDecision(
            pass_ok=pass_ok,
            reason=None,
            will_advance=True,
            next_stage=next_stage_func(stage),
            next_stage_turn=0,
            next_stuck_rounds=0,
            effective_required_pass=thresholds.required_pass,
            effective_min_ai_turns_same_stage=thresholds.min_ai_turns_same_stage,
        )
    return StageProgressDecision(
        pass_ok=pass_ok,
        reason=None,
        will_advance=False,
        next_stage=stage,
        next_stage_turn=new_turn,
        next_stuck_rounds=next_stuck,
        effective_required_pass=thresholds.required_pass,
        effective_min_ai_turns_same_stage=thresholds.min_ai_turns_same_stage,
    )


def resolve_stage_thresholds(
    *,
    required_pass: int,
    min_ai_turns_same_stage: int,
    progression_mode: str = "guided",
    stuck_rounds: int = 0,
    guided_stuck_threshold: int = 4,
    guided_pass_relax: int = 1,
    guided_min_pass: int = 1,
    guided_relax_min_turns: int = 0,
) -> StageThresholds:
    base_required = max(1, int(required_pass))
    base_min_ai_turns = max(0, int(min_ai_turns_same_stage))
    mode = (progression_mode or "guided").strip().lower()

    if mode != "guided":
        return StageThresholds(
            required_pass=base_required,
            min_ai_turns_same_stage=base_min_ai_turns,
        )

    threshold = max(1, int(guided_stuck_threshold))
    stuck = max(0, int(stuck_rounds))
    if stuck < threshold:
        return StageThresholds(
            required_pass=base_required,
            min_ai_turns_same_stage=base_min_ai_turns,
        )

    relaxed_required = max(1, int(guided_min_pass), base_required - max(0, int(guided_pass_relax)))
    relaxed_min_turns = base_min_ai_turns
    if guided_relax_min_turns > 0:
        relaxed_min_turns = max(1, base_min_ai_turns - int(guided_relax_min_turns))

    return StageThresholds(
        required_pass=relaxed_required,
        min_ai_turns_same_stage=relaxed_min_turns,
    )
