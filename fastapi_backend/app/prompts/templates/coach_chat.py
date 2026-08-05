from __future__ import annotations


# Aligned with docs/orid_ai_feedback_rubric.md (odd-week experimental narration).
# Frontend parseFeedbackNarration still accepts legacy aliases.
FEEDBACK_NARRATION_SECTION_TITLES = (
    "你已經做到：",
    "再想一想：",
    "可以這樣修改：",
)

COACH_SOURCE_NOTES = {
    "feedback_button": (
        "學生剛按「取得回饋」並貼上該格草稿；請用**短、自然、國小高年級能懂**的話，"
        "像短卡片，不要長篇分析、不要論文口氣；**不要**幫他寫完整答案。"
    ),
    "default": "學生自由輸入；請延續對話協助草稿，不要改成故事問答闖關。",
}
