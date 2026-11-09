"""Which student-facing weeks are open right now.

Formal experiment weeks are 1..TOTAL_WEEKS. Week 0 is the practice / briefing
sandbox ("系統練習") so teachers can demo without touching research week 1.
"""
from __future__ import annotations

from app.content.week_plan import DEMO_WEEK, is_valid_week

# 0 = lock all formal weeks 1..7. Raise this when the experiment opens each week.
UNLOCKED_FORMAL_WEEKS = 0

# Practice week stays available for briefing / system walkthrough.
DEMO_WEEK_OPEN = True


def is_week_open_for_students(week: int | None) -> bool:
    if not isinstance(week, int) or not is_valid_week(week):
        return False
    if week == DEMO_WEEK:
        return DEMO_WEEK_OPEN
    return 1 <= week <= UNLOCKED_FORMAL_WEEKS
