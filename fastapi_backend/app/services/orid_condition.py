from __future__ import annotations


def normalize_orid_condition(raw: str | None, default: str = "genai") -> str:
    value = (raw or default or "genai").strip().lower()
    if value in {"template", "control"}:
        return "control"
    if value in {"genai", "exp", "experimental"}:
        return "genai"
    return (default or "genai").strip().lower()


def is_control_condition(raw: str | None, default: str = "genai") -> bool:
    return normalize_orid_condition(raw, default=default) == "control"
