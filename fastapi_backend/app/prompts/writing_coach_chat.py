from __future__ import annotations

def _stage_name_zh(stage: str) -> str:
    s = (stage or "O").strip().upper()
    return {"O": "客觀", "R": "感受", "I": "意義", "D": "行動"}.get(s, "這一段")


def _stage_focus_line(stage: str) -> str:
    s = (stage or "O").strip().upper()
    return {
        "O": "O：只談故事裡「發生什麼、先後順序、誰做了什麼」，不要帶進大道理或行動。",
        "R": "R：只談「心情／感受」並用「因為…」連回故事中的某一幕，不要改寫成整篇大意。",
        "I": "I：只談「這代表什麼、提醒了什麼」並用故事細節當理由，不要空喊口號。",
        "D": "D：只談「下次我會做的一個具體小步驟」，要寫得出場景或時機，不要只有決心句。",
    }.get(s, "")


def build_writing_coach_system_prompt(
    *,
    stage: str,
    book_context: str,
    source: str,
) -> str:
    """
    Writing-coach persona: feedback on ORID drafts, not sequential book trivia.
    """
    stage = stage if stage in {"O", "R", "I", "D"} else "O"
    src = (source or "free_text").strip().lower()
    stage_zh = _stage_name_zh(stage)
    focus = _stage_focus_line(stage)

    source_note = ""
    if src == "feedback_button":
        source_note = "學生剛按下「取得回饋」，並附上該格草稿；請先針對草稿給具體、溫和的寫作回饋，最後可留一個很小的追問。"
    else:
        source_note = "學生自由輸入；請延續對話，協助修改草稿或釐清思路，不要改成故事問答闖關。"

    return f"""
你是國小高年級學生的「ORID 寫作回饋同伴」。
{source_note}

【要做的事】
- 聚焦目前討論的 ORID 段：{stage}（{stage_zh}）。{focus}
- 語氣鼓勵、具體、口語；2～5 句為主；不要列點標題、不要像報告。
- 至少一句要明確扣回教材摘要裡「已有」的事件或角色；不要編造書中沒有的細節。
- 不要進行「O→R→I→D 順序聊書」或故事闖關；不要說「現在進入下一階段」。

【不要做】
- 不要批改語氣羞辱或全盤否定。
- 不要要求學生重述整本故事當唯一任務。

【教材】
{book_context or "（未提供）"}
""".strip()


def build_feedback_narration_prompt(
    *,
    stage: str,
    feedback_json_summary: str,
) -> tuple[str, str]:
    """Second-pass LLM: turn structured feedback into a short chat message."""
    focus = _stage_focus_line(stage)
    sys = f"""
你是寫作回饋同伴。請把下列「結構化回饋」改寫成給國小生的 2～4 句聊天訊息。
- 繁體中文、口語、鼓勵
- 不要列點、不要標題、不要 JSON
- 內容必須與結構化回饋一致，不可新增矛盾建議
- 語氣與重點要符合目前 ORID 段：{focus}
目前段落代號：{stage}
""".strip()
    user = f"結構化回饋（請全部涵蓋重點，但用自然話說）：\n{feedback_json_summary}"
    return sys, user


def format_control_feedback_reply(
    *,
    ok: bool,
    missing: list[str],
    suggestions: list[str],
    stage: str,
    book_anchor: str = "",
) -> str:
    """Deterministic chat bubble for control condition (feedback_button path)."""
    stage_zh = _stage_name_zh(stage)
    anchor = (book_anchor or "").strip()
    nudge = ""
    if anchor:
        s = (stage or "O").strip().upper()
        if s == "O":
            nudge = f"故事裡像「{anchor}」這樣的順序，你可以寫進去讓讀的人更跟得上。"
        elif s == "R":
            nudge = f"你可以想著「{anchor}」那一幕，把感受和原因連在一起。"
        elif s == "I":
            nudge = f"若要寫道理，可以用「{anchor}」當例子，說你學到什麼。"
        else:
            nudge = f"若要寫行動，可以想如果是「{anchor}」那種情境，你會先做哪一件小事。"

    if ok:
        core = (
            f"你{stage_zh}這一段已經有抓到重點了，很棒！"
            "如果想再完整一點，可以試著多補一個小細節或一句話，讓讀的人更清楚。"
        )
        return core + (f" {nudge}" if nudge else "")

    parts = []
    if missing:
        parts.append("目前可以再補強的方向：" + "、".join(missing[:3]) + "。")
    if suggestions:
        parts.append("你可以試著：" + "；".join(suggestions[:3]) + "。")
    body = "".join(parts) if parts else "先多寫一點想法，再按一次取得回饋也可以。"
    out = f"我看完你{stage_zh}這一段了。" + body
    if nudge:
        out += " " + nudge
    return out


def format_control_free_text_reply(stage: str) -> str:
    return (
        f"我有看到你的訊息。關於{_stage_name_zh(stage)}這一段，建議你對照教材裡的事件，"
        "把草稿寫具體一點；需要結構化建議時，可以按該格的「取得回饋」。"
    )
