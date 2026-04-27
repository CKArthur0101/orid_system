"""
Prompt bank for AI–ORID system.

- shared.py: shared safety/tone rules + book context formatting
- writing_feedback.py: genai writing feedback prompt builder (Draft1->Draft2)
- writing_assist.py: one-click draft generation prompt builder (Draft1/Draft2)
- writing_coach_chat.py: writing-coach persona + control reply templates
"""

from .shared import ORID_CHAT_SHARED_SYSTEM_RULES, build_book_context_block
from .writing_feedback import build_genai_feedback_prompts
from .writing_assist import ASSIST_TEXT_SPLIT, build_writing_d1_prompts, build_writing_d2_prompts

__all__ = [
    "ORID_CHAT_SHARED_SYSTEM_RULES",
    "build_book_context_block",
    "build_genai_feedback_prompts",
    "ASSIST_TEXT_SPLIT",
    "build_writing_d1_prompts",
    "build_writing_d2_prompts",
]