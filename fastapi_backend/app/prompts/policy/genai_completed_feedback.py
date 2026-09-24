from __future__ import annotations

"""
Deterministic completion-card formatter for the experimental (genai) group only.

When fb_ok=True (rubric level 3 or 4), the backend skips the narration LLM and
emits a short, fixed three-section message instead.  The headings are chosen so
the frontend parser can distinguish "complete" cards from "revision" cards by
looking for 「本階段完成：」 rather than 「你可以再加強：」.

This formatter must NOT be used for control-group paths.
"""

_STAGE_COMPLETE_MSG: dict[str, str] = {
    "O": "O 觀察這一段可以了！你有寫到故事裡的人物和事情，事情怎麼發生也看得出來。",
    "R": "R 感受這一段可以了！你有寫出自己的感覺，也有說為什麼。",
    "I": "I 體會這一段可以了！你有寫出自己學到的想法，也有接回故事。",
    "D": "D 行動這一段可以了！你有寫出一個自己做得到的行動。",
}

_STAGE_NEXT_STEP: dict[str, str] = {
    "O": "接下來去寫 R 感受段：看到這些事，你有什麼感覺？",
    "R": "接下來去寫 I 體會段：這個故事讓你想到或學到什麼？",
    "I": "接下來去寫 D 行動段：下次遇到類似情況，你會怎麼做？",
}

_STAGE_LABELS: dict[str, str] = {
    "O": "O 觀察段",
    "R": "R 感受段",
    "I": "I 體會段",
    "D": "D 行動段",
}

_DEFAULT_PRAISE = "你有認真把這一段寫出來，方向是對的。"


def format_genai_completed_feedback_reply(
    *,
    stage: str,
    praise: str | None,
    completed_stages: set[str] | None = None,
) -> str:
    """
    Return a short deterministic three-section completion message.

    Headings used (for frontend complete-card parser):
      你已經做到：
      本階段完成：
      下一步：

    No modification language.  No further improvement requests.
    """
    s = (stage or "O").strip().upper()
    pr = (praise or "").strip()
    if not pr:
        pr = _DEFAULT_PRAISE
    # Trim praise to ~45 characters so the card stays compact
    if len(pr) > 50:
        pr = pr[:47] + "…"

    completion = _STAGE_COMPLETE_MSG.get(s, f"{s} 這一段可以了！你已經把想法寫清楚了。")
    if s == "D":
        passed = {str(x).strip().upper() for x in (completed_stages or set())}
        missing_stages = [x for x in ("O", "R", "I", "D") if x not in passed]
        if completed_stages is not None and not missing_stages:
            next_step = "四段都完成了！記得按「儲存我的寫作」，完成這次作品。"
        elif completed_stages is None:
            next_step = "D 行動段完成了！請回到寫作頁確認其他段落的完成狀態。"
        else:
            missing_labels = "、".join(_STAGE_LABELS[x] for x in missing_stages)
            next_step = f"D 行動段完成了！還有{missing_labels}尚未完成，請回去繼續寫。"
    else:
        next_step = _STAGE_NEXT_STEP.get(s, "記得儲存你的寫作！")

    return (
        f"你已經做到：\n{pr}\n\n"
        f"本階段完成：\n{completion}\n\n"
        f"下一步：\n{next_step}"
    ).strip()
