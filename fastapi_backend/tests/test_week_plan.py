"""七週流程表：每週的書本、可寫階段、整合來源與可得徽章。"""

from app.content.week_plan import (
    TOTAL_WEEKS,
    badge_ids_available_for_week,
    book_unit_for_week,
    is_orid_week,
    is_synthesis_week,
    is_valid_week,
    orid_source_weeks_for_synthesis,
    reference_weeks,
    stage_source_week,
    task_type_for_week,
    weeks_in_book_unit,
    writable_stages,
)
from app.routes import orid


def test_total_weeks_and_validity():
    assert TOTAL_WEEKS == 7
    assert all(is_valid_week(w) for w in range(1, 8))
    assert not is_valid_week(0)
    assert not is_valid_week(8)


def test_book_units():
    assert [book_unit_for_week(w) for w in range(1, 8)] == [1, 1, 1, 2, 2, 3, 3]
    assert list(weeks_in_book_unit(1)) == [1, 2, 3]
    assert list(weeks_in_book_unit(2)) == [4, 5]
    assert list(weeks_in_book_unit(3)) == [6, 7]


def test_week_kinds():
    assert [is_orid_week(w) for w in range(1, 8)] == [True, True, False, True, False, True, False]
    assert [is_synthesis_week(w) for w in range(1, 8)] == [False, False, True, False, True, False, True]
    assert [task_type_for_week(w) for w in range(1, 8)] == [
        "orid_stage",
        "orid_stage",
        "synthesis",
        "orid_stage",
        "synthesis",
        "orid_stage",
        "synthesis",
    ]


def test_writable_stages_split_for_book_one():
    assert writable_stages(1) == ("O", "R")
    assert writable_stages(2) == ("I", "D")
    assert writable_stages(3) == ()
    assert writable_stages(4) == ("O", "R", "I", "D")
    assert writable_stages(6) == ("O", "R", "I", "D")


def test_reference_and_source_weeks():
    assert reference_weeks(2) == (1,)
    assert reference_weeks(3) == (1, 2)
    assert reference_weeks(5) == (4,)
    assert reference_weeks(7) == (6,)
    assert orid_source_weeks_for_synthesis(3) == (1, 2)
    assert orid_source_weeks_for_synthesis(5) == (4,)
    assert orid_source_weeks_for_synthesis(7) == (6,)
    # Week 3 pulls O/R from week 1 and I/D from week 2; week 2 reads week 1's O/R.
    assert stage_source_week(3, "O") == 1
    assert stage_source_week(3, "D") == 2
    assert stage_source_week(2, "O") == 1
    assert stage_source_week(2, "I") == 2


def test_badges_available_per_week():
    assert badge_ids_available_for_week(1) == ("badge_start", "badge_30")
    assert badge_ids_available_for_week(2) == ("badge_60", "badge_90")
    assert badge_ids_available_for_week(4) == ("badge_start", "badge_30", "badge_60", "badge_90")
    assert badge_ids_available_for_week(3) == (
        "badge_synthesis_content",
        "badge_synthesis_coherence",
        "badge_synthesis_reflection",
        "badge_synthesis_action",
    )


def test_book_packs_follow_the_unit():
    titles = {w: orid.BOOK_PACK_BY_WEEK[w]["book_title"] for w in range(1, 8)}
    assert titles[1] == titles[2] == titles[3] == "阿松爺爺的柿子樹"
    assert titles[4] == titles[5] == "朱家故事"
    assert titles[6] == titles[7] == "不會寫字的獅子"
    assert orid.prior_orid_weeks_for_synthesis(3) == (1, 2)
    assert orid.prior_orid_week_for_synthesis(3) == 2
    assert orid.prior_orid_weeks_for_synthesis(5) == (4,)


def test_stored_reading_with_old_week_numbering_is_remapped():
    """舊 6 週時代的教材列若書名與新週次不符，改用新週次的正式教材包。"""
    from types import SimpleNamespace
    import json

    old_week3_reading = SimpleNamespace(
        title="第 3 週（暫定教材）",
        content=json.dumps(orid.BOOK_PACK_BY_WEEK[4], ensure_ascii=False),
    )
    pack = orid.load_book_pack_from_reading(old_week3_reading)
    assert pack["book_title"] == "阿松爺爺的柿子樹"
