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
    "O": "O 客觀事實階段完成！你已經把故事裡的人物和事件說清楚了。",
    "R": "R 感受階段完成！你已經把自己的感受和原因說清楚了。",
    "I": "I 意義階段完成！你已經寫出從故事裡學到了什麼。",
    "D": "D 行動階段完成！你已經寫出之後想怎麼做了。",
}

_STAGE_NEXT_STEP: dict[str, str] = {
    "O": "接下來可以進入 R，試著寫寫看：這個故事哪一幕讓你印象最深？你有什麼感覺？",
    "R": "接下來可以進入 I，試著想想：這個故事讓你明白了什麼道理？",
    "I": "接下來可以進入 D，試著寫寫看：讀完之後，你在生活裡想怎麼做？",
    "D": "四格都完成了！記得按「儲存我的寫作」把內容存起來。",
}

_DEFAULT_PRAISE = "你有認真把這一段寫出來，方向是對的。"


def format_genai_completed_feedback_reply(
    *,
    stage: str,
    praise: str | None,
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

    completion = _STAGE_COMPLETE_MSG.get(s, f"{s} 階段完成！你已經把這一段寫清楚了。")
    next_step = _STAGE_NEXT_STEP.get(s, "記得儲存你的寫作！")

    return (
        f"你已經做到：\n{pr}\n\n"
        f"本階段完成：\n{completion}\n\n"
        f"下一步：\n{next_step}"
    ).strip()
