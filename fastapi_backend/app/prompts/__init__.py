"""
Prompt stack for the ORID system.

Compatibility imports remain at the top level, while the real implementation
now lives under builders/policy/parsers/shared_parts/templates.
"""

from .shared import ORID_CHAT_SHARED_SYSTEM_RULES, build_book_context_block
from .writing_feedback import build_genai_feedback_prompts
from .writing_assist import (
    ASSIST_TEXT_SPLIT,
    build_writing_d1_prompts,
    build_writing_d2_prompts,
    parse_writing_assist_response,
)
from .writing_coach_chat import (
    build_feedback_narration_prompt,
    build_synthesis_coach_system_prompt,
    build_writing_coach_system_prompt,
    detect_feedback_strength,
    format_control_feedback_reply,
    format_control_free_text_reply,
    normalize_feedback_focus,
)
from .orid_checker import (
    build_book_grounding_checker_prompts,
    parse_book_grounding_checker_json,
)

__all__ = [
    "ORID_CHAT_SHARED_SYSTEM_RULES",
    "build_book_context_block",
    "build_genai_feedback_prompts",
    "ASSIST_TEXT_SPLIT",
    "parse_writing_assist_response",
    "build_writing_d1_prompts",
    "build_writing_d2_prompts",
    "build_feedback_narration_prompt",
    "build_synthesis_coach_system_prompt",
    "build_writing_coach_system_prompt",
    "detect_feedback_strength",
    "format_control_feedback_reply",
    "format_control_free_text_reply",
    "normalize_feedback_focus",
    "build_book_grounding_checker_prompts",
    "parse_book_grounding_checker_json",
]