"""Per-account login failure lock. The password is never stored here."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

LOCK_AFTER = 8
LOCK_FOR = timedelta(minutes=15)


@dataclass
class LockState:
    fail_count: int = 0
    locked_until: datetime | None = None


def _aware(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def is_locked(state: LockState, now: datetime) -> bool:
    if state.locked_until is None:
        return False
    return _aware(state.locked_until) > _aware(now)


def record_failure(state: LockState, now: datetime) -> LockState:
    moment = _aware(now)
    if is_locked(state, moment):
        return state
    previous = 0 if state.locked_until is not None and _aware(state.locked_until) <= moment else state.fail_count
    count = previous + 1
    locked_until = moment + LOCK_FOR if count >= LOCK_AFTER else None
    return LockState(fail_count=count, locked_until=locked_until)


def record_success() -> LockState:
    return LockState()
