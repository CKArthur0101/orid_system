"""Unit tests for classify_student_input and excerpt helper."""

from app.prompts.policy.student_input_bucket import (
    BUCKET_EMPTY,
    BUCKET_LATIN_HEAVY,
    BUCKET_LIKELY_GIBBERISH,
    BUCKET_MIXED_SCRIPT,
    BUCKET_NORMAL,
    BUCKET_TOO_SHORT,
    classify_student_input,
    truncate_student_draft_excerpt,
)


def test_classify_empty():
    assert classify_student_input("") == BUCKET_EMPTY
    assert classify_student_input("   \n") == BUCKET_EMPTY


def test_classify_too_short():
    assert classify_student_input("短") == BUCKET_TOO_SHORT
    assert classify_student_input("你好") == BUCKET_TOO_SHORT


def test_classify_likely_gibberish():
    assert classify_student_input("aaaaaaaaaa") == BUCKET_LIKELY_GIBBERISH
    assert classify_student_input("asdfasdfasdfasdf") == BUCKET_LIKELY_GIBBERISH


def test_classify_mixed_script():
    t = "我今天 feel happy about the story 阿松爺爺"
    assert classify_student_input(t) == BUCKET_MIXED_SCRIPT


def test_classify_latin_heavy():
    t = "I think the grandfather hid the persimmons in the warehouse behind his house."
    assert classify_student_input(t) == BUCKET_LATIN_HEAVY


def test_classify_normal_cjk():
    t = "阿松爺爺把柿子藏到屋後倉庫，最後大家一起分享，我覺得分享很重要。"
    assert classify_student_input(t) == BUCKET_NORMAL


def test_truncate_excerpt():
    long = "字" * 300
    out = truncate_student_draft_excerpt(long, max_len=50)
    assert len(out) == 50
    assert out.endswith("…")


def test_pick_variant_stable():
    from app.prompts.playbook_variants import pick_variant

    a = pick_variant("user:session:7", "normal")
    b = pick_variant("user:session:7", "normal")
    assert a == b
    assert len(a) >= 4


def test_skip_book_grounding_enforcement():
    from app.prompts.policy.student_input_bucket import skip_book_grounding_enforcement

    assert skip_book_grounding_enforcement("likely_gibberish") is True
    assert skip_book_grounding_enforcement("too_short") is True
    assert skip_book_grounding_enforcement("empty") is True
    assert skip_book_grounding_enforcement("normal") is False
    assert skip_book_grounding_enforcement("latin_heavy") is False
