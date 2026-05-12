"""
Compatibility wrapper for checker-related prompt modules.

The active runtime now consumes builders/policy/parsers directly; legacy checker
entry points are re-exported here so older imports do not break.
"""

from app.prompts.builders.checker import (
    build_book_grounding_checker_prompts,
    build_orid_checker_prompts,
)
from app.prompts.parsers.json_payloads import (
    parse_book_grounding_checker_json,
    parse_orid_checker_json,
)
from app.prompts.policy.checker_fallbacks import clamp_checker_output, quick_unsafe_check
from app.prompts.policy.grounding import (
    looks_obviously_offtopic,
    looks_likely_factual_mismatch,
    looks_likely_latin_hallucination,
    looks_likely_ungrounded_in_book,
    looks_story_related_to_book,
)

__all__ = [
    "build_book_grounding_checker_prompts",
    "build_orid_checker_prompts",
    "parse_book_grounding_checker_json",
    "parse_orid_checker_json",
    "clamp_checker_output",
    "quick_unsafe_check",
    "looks_story_related_to_book",
    "looks_obviously_offtopic",
    "looks_likely_latin_hallucination",
    "looks_likely_factual_mismatch",
    "looks_likely_ungrounded_in_book",
]