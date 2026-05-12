"""Compatibility wrapper for shared prompt helpers."""

from app.prompts.shared_parts.book_context import (
    ORID_CHAT_SHARED_SYSTEM_RULES,
    build_book_context_block,
)

__all__ = ["ORID_CHAT_SHARED_SYSTEM_RULES", "build_book_context_block"]
