"""Seven-week intervention plan (student-facing week numbers 1–7).

Book 1 is split into three weeks: O/R, then I/D, then the integrated piece.
Books 2 and 3 keep one ORID week followed by one integration week.

    1  阿松爺爺的柿子樹            O・R
    2  阿松爺爺的柿子樹            I・D   (reads week 1 O/R)
    3  阿松爺爺的柿子樹（整合寫作）       (reads week 1 O/R + week 2 I/D)
    4  朱家故事                    O・R・I・D
    5  朱家故事（整合寫作）               (reads week 4)
    6  不會寫字的獅子              O・R・I・D
    7  不會寫字的獅子（整合寫作）         (reads week 6)

Keep in sync with nextjs-frontend/lib/orid/week-flow.ts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

TOTAL_WEEKS = 7
STAGE_KEYS: tuple[str, ...] = ("O", "R", "I", "D")


@dataclass(frozen=True)
class WeekPlan:
    week: int
    kind: str  # "orid" | "synthesis"
    book_unit: int
    stages: tuple[str, ...] = field(default_factory=tuple)
    reference_weeks: tuple[int, ...] = field(default_factory=tuple)


WEEK_PLAN: dict[int, WeekPlan] = {
    1: WeekPlan(1, "orid", 1, ("O", "R"), ()),
    2: WeekPlan(2, "orid", 1, ("I", "D"), (1,)),
    3: WeekPlan(3, "synthesis", 1, (), (1, 2)),
    4: WeekPlan(4, "orid", 2, STAGE_KEYS, ()),
    5: WeekPlan(5, "synthesis", 2, (), (4,)),
    6: WeekPlan(6, "orid", 3, STAGE_KEYS, ()),
    7: WeekPlan(7, "synthesis", 3, (), (6,)),
}


def is_valid_week(week: int | None) -> bool:
    return isinstance(week, int) and week in WEEK_PLAN


def is_synthesis_week(week: int) -> bool:
    plan = WEEK_PLAN.get(week)
    return plan is not None and plan.kind == "synthesis"


def is_orid_week(week: int) -> bool:
    plan = WEEK_PLAN.get(week)
    return plan is not None and plan.kind == "orid"


def writable_stages(week: int) -> tuple[str, ...]:
    plan = WEEK_PLAN.get(week)
    return plan.stages if plan else ()


def reference_weeks(week: int) -> tuple[int, ...]:
    plan = WEEK_PLAN.get(week)
    return plan.reference_weeks if plan else ()


def book_unit_for_week(week: int) -> int:
    plan = WEEK_PLAN.get(week)
    return plan.book_unit if plan else 1


def weeks_in_book_unit(book_unit: int) -> list[int]:
    return [w for w, p in WEEK_PLAN.items() if p.book_unit == book_unit]


def first_week_of_book_unit(week: int) -> int:
    weeks = weeks_in_book_unit(book_unit_for_week(week))
    return min(weeks) if weeks else week


def book_pack_week(week: int) -> int:
    """The first ORID week of the unit; its pack is the book for every week in the unit."""
    return first_week_of_book_unit(week)


def task_type_for_week(week: int) -> str:
    return "synthesis" if is_synthesis_week(week) else "orid_stage"


def stage_source_week(week: int, stage: str) -> int | None:
    """Which week holds the saved text for `stage` when viewed from `week`."""
    if stage in writable_stages(week):
        return week
    for ref in reference_weeks(week):
        if stage in writable_stages(ref):
            return ref
    return None


def orid_source_weeks_for_synthesis(week: int) -> tuple[int, ...]:
    """ORID weeks an integration week reads: 3→(1,2), 5→(4,), 7→(6,)."""
    return reference_weeks(week) if is_synthesis_week(week) else ()


def badge_ids_available_for_week(week: int) -> tuple[str, ...]:
    """Stage badges a student can newly earn in this week.

    Week 1 (O/R only): start + bronze. Week 2 (I/D): silver + gold, judged on
    week 1 O/R together with this week's I/D. Full ORID weeks: all four.
    Integration weeks: the four synthesis badges.
    """
    if is_synthesis_week(week):
        return (
            "badge_synthesis_content",
            "badge_synthesis_coherence",
            "badge_synthesis_reflection",
            "badge_synthesis_action",
        )
    stages = set(writable_stages(week))
    if stages == {"O", "R"}:
        return ("badge_start", "badge_30")
    if stages == {"I", "D"}:
        return ("badge_60", "badge_90")
    return ("badge_start", "badge_30", "badge_60", "badge_90")
