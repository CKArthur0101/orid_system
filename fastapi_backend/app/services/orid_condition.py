from __future__ import annotations

# Session-level values used by OridSession.condition
SESSION_GENAI = "genai"
SESSION_CONTROL = "control"

# User-level values stored on User.orid_condition
USER_EXPERIMENTAL = "experimental"
USER_CONTROL = "control"

CONTROL_AI_FORBIDDEN_DETAIL = "控制組不提供個人化 AI 回饋，請使用固定寫作提示。"


def normalize_orid_condition(raw: str | None, default: str = SESSION_GENAI) -> str:
    """Normalize aliases to session condition: genai | control."""
    value = (raw or default or SESSION_GENAI).strip().lower()
    if value in {"template", "control"}:
        return SESSION_CONTROL
    if value in {"genai", "exp", "experimental"}:
        return SESSION_GENAI
    return (default or SESSION_GENAI).strip().lower()


def is_control_condition(raw: str | None, default: str = SESSION_GENAI) -> bool:
    return normalize_orid_condition(raw, default=default) == SESSION_CONTROL


def is_genai_condition(raw: str | None, default: str = SESSION_GENAI) -> bool:
    return normalize_orid_condition(raw, default=default) == SESSION_GENAI


def session_condition_from_user_orid_condition(raw: str | None) -> str:
    """Map User.orid_condition → session condition; missing/unknown → genai (experimental)."""
    return normalize_orid_condition(raw or USER_EXPERIMENTAL, default=SESSION_GENAI)
