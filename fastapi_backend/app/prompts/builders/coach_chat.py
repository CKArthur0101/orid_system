from __future__ import annotations

from app.prompts.shared_parts.stage_text import stage_focus_line, stage_name_zh
from app.prompts.templates.coach_chat import (
    COACH_SOURCE_NOTES,
    FEEDBACK_NARRATION_SECTION_TITLES,
)


def build_synthesis_coach_system_prompt(
    *,
    book_context: str,
    week1_orid_lines: dict[str, str],
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
    return f"""
你是國小高年級學生的寫作回饋同伴。
學生要把第 1 週四段 ORID **整合**成一段（或一篇短文）連貫的心得。
請針對學生貼上的【整合草稿】回饋：段落銜接、是否仍扣緊故事、哪裡再多一句會更清楚。
用短段落、口語、繁體中文；**不要**代寫整篇交作業用的完整範文。

【第 1 週四段（唯讀參考）】
{joined}

【教材脈絡】
{book_context or "（未提供）"}
""".strip()


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
    stage_zh = stage_name_zh(stage)
    focus = stage_focus_line(stage)
    source_note = COACH_SOURCE_NOTES.get(src, COACH_SOURCE_NOTES["default"])

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
    focus = stage_focus_line(stage)
    title_done, title_missing, title_try = FEEDBACK_NARRATION_SECTION_TITLES
    sys = f"""
你是寫作回饋同伴。下面是一份「結構化回饋」JSON。請改寫成給**國小高年級**讀的訊息，**剛好三段**，標題必須是（字可微調，但三段結構與順序不變）：

{title_done}
{title_missing}
{title_try}

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
