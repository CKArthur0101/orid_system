from app.services.orid_condition import (
    is_control_condition,
    is_genai_condition,
    normalize_orid_condition,
    session_condition_from_user_orid_condition,
)


def test_normalize_aliases():
    assert normalize_orid_condition("experimental") == "genai"
    assert normalize_orid_condition("exp") == "genai"
    assert normalize_orid_condition("genai") == "genai"
    assert normalize_orid_condition("control") == "control"
    assert normalize_orid_condition("template") == "control"


def test_normalize_unknown_falls_back_to_default():
    assert normalize_orid_condition("A", default="genai") == "genai"
    assert normalize_orid_condition("weird", default="control") == "control"
    assert normalize_orid_condition(None) == "genai"
    assert normalize_orid_condition("") == "genai"


def test_session_condition_from_user_orid_condition():
    assert session_condition_from_user_orid_condition("experimental") == "genai"
    assert session_condition_from_user_orid_condition("exp") == "genai"
    assert session_condition_from_user_orid_condition("control") == "control"
    assert session_condition_from_user_orid_condition(None) == "genai"
    # Typos / nonstandard imports that used to become control now map via aliases or default
    assert session_condition_from_user_orid_condition("genai") == "genai"


def test_is_control_and_genai_helpers():
    assert is_control_condition("control") is True
    assert is_genai_condition("experimental") is True
    assert is_control_condition("experimental") is False
