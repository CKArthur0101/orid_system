from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StageProgressDecision:
    pass_ok: bool
    reason: str | None
    will_advance: bool
    next_stage: str
    next_stage_turn: int


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
) -> StageProgressDecision:
    stage = (current_stage or "O").strip().upper()
    new_turn = stage_turn + 1 if pass_ok else stage_turn
    will_advance = (
        pass_ok
        and stage != "D"
        and new_turn >= required_pass
        and ai_count_same_stage >= min_ai_turns_same_stage
    )
    if will_advance:
        return StageProgressDecision(
            pass_ok=pass_ok,
            reason=None,
            will_advance=True,
            next_stage=next_stage_func(stage),
            next_stage_turn=0,
        )
    return StageProgressDecision(
        pass_ok=pass_ok,
        reason=None,
        will_advance=False,
        next_stage=stage,
        next_stage_turn=new_turn,
    )
