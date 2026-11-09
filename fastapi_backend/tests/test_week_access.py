from app.content.week_access import (
    DEMO_WEEK_OPEN,
    UNLOCKED_FORMAL_WEEKS,
    is_week_open_for_students,
)


def test_practice_week_open_while_formal_weeks_locked():
    assert UNLOCKED_FORMAL_WEEKS == 0
    assert DEMO_WEEK_OPEN is True
    assert is_week_open_for_students(0) is True
    for week in range(1, 8):
        assert is_week_open_for_students(week) is False
    assert is_week_open_for_students(99) is False
    assert is_week_open_for_students(None) is False
