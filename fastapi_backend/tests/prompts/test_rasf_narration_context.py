"""Tests for RASF narration context builder."""
from __future__ import annotations

from app.prompts.policy.rasf_narration_context import build_rasf_narration_context


def test_build_rasf_narration_context_o_level2():
    book_pack = {
        "writing_rubric": {
            "by_stage": {
                "O": [
                    {
                        "id": "O1",
                        "levels": [
                            {"label": "1 起步", "desc": "只有感想"},
                            {"label": "2 接近", "desc": "有事件但零散"},
                            {"label": "3 達標", "desc": "至少一件重要事件清楚"},
                        ],
                    }
                ]
            }
        }
    }
    ctx = build_rasf_narration_context(
        stage="O",
        book_pack=book_pack,
        rubric_focus="O1",
        rubric_level_estimate={"O1": "2 接近"},
        student_anchor_quote="用柿子蒂打陀螺",
        draft_next_step="在這句前面補上哎唷奶奶",
    )
    assert ctx["focus"] == "O1"
    assert ctx["current_level"] == 2
    assert ctx["current_level_plain"] == "有事件但零散"
    assert ctx["next_level_plain"] == "至少一件重要事件清楚"
    assert ctx["student_anchor_quote"] == "用柿子蒂打陀螺"
    assert "哎唷奶奶" in ctx["draft_next_step"]
