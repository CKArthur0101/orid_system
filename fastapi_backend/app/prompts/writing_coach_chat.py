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
        source_note = (
            "學生剛按「取得回饋」並貼上該格草稿；請用**短、自然、國小高年級能懂**的話，"
            "像短卡片，不要長篇分析、不要論文口氣；**不要**幫他寫完整答案。"
        )
    else:
        source_note = "學生自由輸入；請延續對話協助草稿，不要改成故事問答闖關。"

    return f"""
你是國小高年級學生的「ORID 寫作回饋同伴」。
{source_note}

【要做的事】
- 只談目前段：{stage}（{stage_zh}）。{focus}
- 至少一句要扣回教材底下已出現的角色或事件；不要編造書裡沒有的細節。
- 若內容與教材明顯不符，先溫和說明再引導對齊摘要。
- 不要說「現在進入下一階段」或帶闖關。

【不要做】
- 不要羞辱、不要一次列很多缺點、不要代寫整段。

【教材】
{book_context or "（未提供）"}
""".strip()


def build_feedback_narration_prompt(
    *,
    stage: str,
    feedback_json_summary: str,
) -> tuple[str, str]:
    """第二段 LLM：把 JSON 變成三段式短訊息（與使用者可讀格式一致）。"""
    focus = _stage_focus_line(stage)
    sys = f"""
你是寫作回饋同伴。下面是一份「結構化回饋」JSON。請改寫成給**國小高年級**讀的訊息，**剛好三段**，標題必須是（字可微調，但三段結構與順序不變）：

你已經做到：
你可以再加強：
試試看這樣寫：

【品質（務必遵守）】
- 繁體中文；**整體偏短**，三段加起來不要像作文批改，**不要超過約 15 行**。
- 第一段（你已經做到）：**必須**讓人覺得你有讀學生草稿，盡量點出原文裡的人、事、感受或行動；**禁止**只有「你有先寫下想法／你很努力」這類空泛句（若 JSON 的 praise 已有具體內容，請保留並潤飾得更口語）。
- 第二段（你可以再加強）：**只一個**主點，符合 {stage} 段目標（{focus}）；不要列兩三個缺點；**禁止**出現「深化內容、增加完整度、補充細節」但不說要補什麼的那種空話；若內容偏短，要**說出還差哪一類內容**（例如還沒寫是誰、還沒寫因為、還沒寫怎麼做），不要只寫「太短」兩字結束。
- 第三段（試試看）：要是**學生接下去就能寫的**口語，優先像「故事裡先發生的是……」「我覺得……，因為……」「這件事讓我明白……」「下次遇到……，我會……」**禁止**只寫「請補充更多細節、請用句號寫出一件事、試著增加內容完整度」這類難以接寫的指令。
- 不要產生一整段可交作業的範文；不要輸出 JSON、不要 ```。
- 本段代號：{stage}
""".strip()
    user = f"結構化回饋 JSON：\n{feedback_json_summary}"
    return sys, user


def _praise_line_from_draft(t: str, stage: str) -> str:
    """從學生草稿截一小段用於稱讚，避免全篇罐頭句（無 LLM 或 praise 不具體時）。"""
    t = (t or "").strip()
    s = (stage or "O").strip().upper()
    stage_zh = _stage_name_zh(s)
    if not t:
        return "你願意寫，我已經看到了，我們一起再補一小步就好。"

    one = t.replace("\n", " ")
    for sep in ("。", "！", "？", "，"):
        if sep in one:
            one = one.split(sep, 1)[0].strip()
            break
    if len(one) > 36:
        one = one[:36] + "…"
    return f"你有寫到「{one}」，看得出你在寫「{stage_zh}」這一段囉。"


def _is_generic_praise(p: str) -> bool:
    p = (p or "").strip()
    if not p:
        return True
    if "先把想法寫在紙上" in p:
        return True
    # 舊控制組 ok 用語：你「客觀」…有寫到重點
    if "有寫到重點" in p and "不錯喔" in p and "你「" in p:
        return True
    return False


def format_control_feedback_reply(
    *,
    ok: bool,
    missing: list[str],
    suggestions: list[str],
    stage: str,
    book_anchor: str = "",
    praise: str | None = None,
    student_draft: str = "",
) -> str:
    """控制組／無第二段 LLM 時的確定性三段式；語意貼近 GenAI 規則。"""
    m0 = (missing[0] if missing else "").strip()
    s0 = (suggestions[0] if suggestions else "").strip()
    anchor = (book_anchor or "").strip()
    nudge = ""
    if anchor:
        s_up = (stage or "O").strip().upper()
        if s_up == "O":
            nudge = f"還能想一想摘要裡像「{anchor}」先後怎麼發生，照順序寫一句就更好懂。"
        elif s_up == "R":
            nudge = f"從故事裡「{anchor}」想起某一幕，用「我覺得……，因為……」接下去寫也可以。"
        elif s_up == "I":
            nudge = f"用「{anchor}」帶出一句你學到什麼，再補一個小理由就好。"
        else:
            nudge = f"想成「{anchor}」那種情況時，你下次會多做的那一個小行動是什麼？"

    pr = (praise or "").strip()
    if "對齊教材" in m0:
        line1 = "你有試著寫出人物和事件，這是 O 段需要的方向；只是情節要再對回書裡。"
    elif _is_generic_praise(pr) and (student_draft or "").strip():
        line1 = _praise_line_from_draft(student_draft, stage)
    elif pr and not _is_generic_praise(pr):
        line1 = pr
    else:
        line1 = _praise_line_from_draft(student_draft, stage) if (student_draft or "").strip() else (pr or "你有試著寫，我已經看到了。")

    if ok:
        line2 = m0 if m0 else "如果想再寫好一點，只要多一個小重點就好。"
    else:
        line2 = m0 if m0 else "我們只先改一處，就會有幫助。"

    if s0 and "用。結尾" in s0:
        line3 = "故事裡先發生的是……，你再用一句寫出後來又怎樣，就很清楚了。"
    elif "對齊教材" in m0:
        line3 = "故事裡先發生的是……，後來……；請用書中真的人物和事件接下去。"
    elif s0 and not any(
        x in s0 for x in ("補充更多細節", "內容完整度", "深化內容", "增加完整度")
    ):
        line3 = s0
    elif nudge:
        line3 = nudge
    else:
        line3 = "用一句你平常會說的話起頭，再補兩三個字就夠了。"

    return (
        f"你已經做到：\n{line1}\n\n"
        f"你可以再加強：\n{line2}\n\n"
        f"試試看這樣寫：\n{line3}"
    ).strip()


def format_control_free_text_reply(stage: str) -> str:
    return (
        f"我有看到你的訊息。關於{_stage_name_zh(stage)}這一段，建議你對照教材裡的事件，"
        "把草稿寫具體一點；需要結構化建議時，可以按該格的「取得回饋」。"
    )
