from __future__ import annotations

from typing import Optional

from app.prompts.orid_playbook import (
    format_feedback_narration_playbook,
    format_synthesis_coach_playbook,
    format_writing_coach_playbook,
)
from app.prompts.shared_parts.stage_text import stage_focus_line, stage_name_zh
from app.prompts.templates.coach_chat import (
    COACH_SOURCE_NOTES,
    FEEDBACK_NARRATION_SECTION_TITLES,
)


def build_synthesis_coach_system_prompt(
    *,
    book_context: str,
    week1_orid_lines: dict[str, str],
    student_display_name: Optional[str] = None,
    student_login: Optional[str] = None,
    opening_hint: str = "",
    prev_ai_opener: Optional[str] = None,
) -> str:
    """
    Week-2 synthesis: feedback on the student's integrated paragraph using Week-1 ORID slots as context.
    """
    labels = {"O": "O 客觀", "R": "R 感受", "I": "I 意義", "D": "D 行動"}
    lines: list[str] = []
    for k in ["O", "R", "I", "D"]:
        t = (week1_orid_lines.get(k) or "").strip()
        lines.append(f"- {labels[k]}：{t or '（尚未撰寫）'}")
    joined = "\n".join(lines)
    hint = opening_hint or "先鎖定一段最想讀者跟上你的地方，再補一句銜接。"
    return format_synthesis_coach_playbook(
        week1_block=joined,
        book_context=book_context,
        student_display_name=student_display_name,
        student_login=student_login,
        opening_hint=hint,
        prev_ai_opener=prev_ai_opener,
    )


def build_writing_coach_system_prompt(
    *,
    stage: str,
    book_context: str,
    source: str,
    student_display_name: Optional[str] = None,
    student_login: Optional[str] = None,
    input_bucket: str = "normal",
    opening_hint: str = "",
    prev_ai_opener: Optional[str] = None,
) -> str:
    """
    Writing-coach persona: feedback on ORID drafts, not sequential book trivia.
    """
    stage = stage if stage in {"O", "R", "I", "D"} else "O"
    src = (source or "free_text").strip().lower()
    stage_zh = stage_name_zh(stage)
    focus = stage_focus_line(stage)
    source_note = COACH_SOURCE_NOTES.get(src, COACH_SOURCE_NOTES["default"])
    stage_scope = f"{stage}（{stage_zh}）"
    hint = opening_hint or "先把你最想被看懂的一句寫清楚。"
    return format_writing_coach_playbook(
        stage_scope=stage_scope,
        focus=focus,
        source_note=source_note,
        book_context=book_context,
        student_display_name=student_display_name,
        student_login=student_login,
        input_bucket=input_bucket,
        opening_hint=hint,
        prev_ai_opener=prev_ai_opener,
    )


def build_feedback_narration_prompt(
    *,
    stage: str,
    feedback_json_summary: str,
    student_display_name: Optional[str] = None,
    student_login: Optional[str] = None,
    student_draft_excerpt: str = "",
    input_bucket: str = "normal",
    opening_hint: str = "",
    prev_ai_opener: Optional[str] = None,
) -> tuple[str, str]:
    """第二段 LLM：把 JSON 變成三段式可讀回饋，保留可直接續寫的引導。"""
    focus = stage_focus_line(stage)
    title_done, title_missing, title_try = FEEDBACK_NARRATION_SECTION_TITLES
    excerpt = (student_draft_excerpt or "").strip() or "（無內容）"
    hint = opening_hint or "先把你最想被看懂的一句寫清楚。"
    sys = format_feedback_narration_playbook(
        stage=stage,
        focus=focus,
        title_done=title_done,
        title_missing=title_missing,
        title_try=title_try,
        student_display_name=student_display_name,
        student_login=student_login,
        student_draft_excerpt=excerpt,
        input_bucket=input_bucket,
        opening_hint=hint,
        prev_ai_opener=prev_ai_opener,
    )
    user = (
        f"【輸入粗分類】{input_bucket}\n"
        f"【學生草稿摘錄】\n{excerpt}\n\n"
        f"結構化回饋 JSON：\n{feedback_json_summary}"
    )
    return sys, user
