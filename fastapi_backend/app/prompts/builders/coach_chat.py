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

_SYNTHESIS_PHASE_CHOICES = frozenset({"select_evidence", "align_prompt", "short_draft", "expand_revise"})


def looks_like_pasted_stage_paragraphs(
    text: str, week1_orid_lines: Optional[dict[str, str]] = None
) -> bool:
    """True when the draft contains 3+ of the Week-1 O/R/I/D lines verbatim.

    Matches the「用複製 O/R/I/D 按鈕直接貼上」pattern exactly (the 複製 button
    appends the stored stage text unchanged), which is a far more reliable
    signal than guessing from connector words — plenty of genuine ORID stage
    text naturally opens with phrases like「這件事讓我學到」.
    """
    t = (text or "").strip()
    if not t or not week1_orid_lines:
        return False
    hits = 0
    for key in ("O", "R", "I", "D"):
        line = (week1_orid_lines.get(key) or "").strip()
        if len(line) >= 8 and line in t:
            hits += 1
    return hits >= 3


_SYNTHESIS_RUBRICS: tuple[tuple[str, str], ...] = (
    ("完整性", "文章是否包含故事事件、感受、體會與未來行動四個部分？"),
    ("連貫性", "句子之間是否順暢？不是把四段硬貼在一起，而是有串接。"),
    ("反思深度", "學生是否說明原因、想法、體會，並能從故事連結到自己？"),
    ("行動具體性", "D 的部分是否具體？學生是否說出實際能做到的行動？"),
)


def _synthesis_phase_zh(phase: str) -> str:
    return {
        "select_evidence": "階段 A：選證據／帶材料",
        "align_prompt": "階段 B：對齊題幹（鷹架句）",
        "short_draft": "階段 C：短初稿",
        "expand_revise": "階段 D：擴寫／修訂",
    }.get(phase, phase)


def _synthesis_operational_instructions(
    *,
    phase: Optional[str],
    feedback_round: int,
    synthesis_clarify: bool,
) -> str:
    """分階、分層、兩輪制；phase 為 None 且僅第二輪時給精簡第二輪說明。"""
    r1 = feedback_round == 1
    lines: list[str] = []

    if phase and phase in _SYNTHESIS_PHASE_CHOICES:
        lines.append(f"【當前寫作階段】{_synthesis_phase_zh(phase)}")
        layer, rubric_ids = _synthesis_layer_and_rubrics(phase=phase, feedback_round=feedback_round)
        lines.append(f"【本輪回饋層級（只談這一層為主，必要時一句帶過其他）】\n{layer}")
        rubric_lines = [f"- {rid}：{text}" for rid, text in _SYNTHESIS_RUBRICS if rid in rubric_ids]
        lines.append("【本輪檢查重點（對照下列 1～2 條即可）】\n" + "\n".join(rubric_lines))
    elif not r1:
        lines.append("【本輪為第二輪】可在連貫性、反思深度與行動具體性上給較具體建議，仍以短段落、不要代寫全文。")
        lines.append(
            "【本輪檢查重點（對照下列 1～2 條即可）】\n"
            "- 連貫性：段落之間有銜接，先說什麼、再說什麼不會突然跳走。\n"
            "- 行動具體性：D 的部分是否具體說出實際能做到的行動？"
        )

    if r1:
        lines.append(
            "【兩輪制／份量】這是**第一輪**：請**只給「一個」最小下一步**（一句方向 + 可選半句示例提示），"
            "不要一次列很多缺點、不要代寫整段。"
        )
    else:
        lines.append(
            "【兩輪制／份量】這是**第二輪**：可以再多一小層（例如補一句銜接或一個更清楚的例子），"
            "仍請維持短段落，不要代寫整篇。"
        )

    if synthesis_clarify:
        lines.append(
            "【可選澄清】若你覺得缺少關鍵資訊才能回饋，可在整段文字**最末另起一行**，"
            "用「想問你：……」**只問一個**極短的問題；不要放在開頭、不要多問。"
        )

    return "\n\n".join(lines)


def _synthesis_layer_and_rubrics(*, phase: str, feedback_round: int) -> tuple[str, frozenset[str]]:
    """回傳（層級說明, rubric id 集合）。"""
    r2 = feedback_round == 2
    if phase == "select_evidence":
        if not r2:
            return "完整性為主：文章是否包含故事事件、感受、體會與未來行動？", frozenset({"完整性", "反思深度"})
        return "完整性為主，並輕輕點一下各部分是否有串接。", frozenset({"完整性", "連貫性"})
    if phase == "align_prompt":
        if not r2:
            return "連貫性為主：句子之間是否有銜接，不是只把四段硬貼在一起？", frozenset({"連貫性", "完整性"})
        return "連貫性與反思深度：文章是否能從故事連結到自己的想法？", frozenset({"連貫性", "反思深度"})
    if phase == "short_draft":
        if not r2:
            return "完整性與連貫性：短稿是否有各部分，讀者看得懂主線。", frozenset({"完整性", "連貫性"})
        return "反思深度：學生是否說明原因並連結到自己？", frozenset({"反思深度", "行動具體性"})
    # expand_revise
    if not r2:
        return "反思深度與行動具體性：體會是否清楚？未來行動是否具體可做？", frozenset({"反思深度", "行動具體性"})
    return "行動具體性為主：D 的部分是否具體說出實際能做到的行動？", frozenset({"行動具體性", "連貫性"})


def compose_synthesis_coach_mid_block(
    *,
    synthesis_phase: Optional[str],
    feedback_round: int,
    reading_excerpt: Optional[str],
    synthesis_clarify: bool,
    looks_pasted: bool = False,
) -> str:
    """
    Inserted between 【教材脈絡】 and personal tail.
    Empty when legacy defaults (round 1, no phase, no excerpt, no clarify).
    """
    pieces: list[str] = []
    rex = (reading_excerpt or "").strip()
    if rex:
        cap = rex[:2000]
        tail_note = "\n（以上節選已截斷至約 2000 字）" if len(rex) > 2000 else ""
        pieces.append(f"【學生自填閱讀心得／摘記節選（唯讀）】\n{cap}{tail_note}")

    if looks_pasted:
        pieces.append(
            "【偵測】草稿看起來像是把上週幾段（觀察／感受／體會／行動）直接貼上、段落之間還沒加銜接語。"
            "這種情況通常代表「完整性」已經有了；本輪回饋請優先只看「連貫性」這一項："
            "先肯定四個部分都在了，再只指出「哪兩段之間」可以加一句銜接、"
            "並給一個銜接語或連接詞的小範例即可；**不要**要求整篇重寫、**不要**要求把每一段都改寫。"
        )

    phase = synthesis_phase if (synthesis_phase or "") in _SYNTHESIS_PHASE_CHOICES else None
    rnd = 2 if int(feedback_round) == 2 else 1

    if phase or rnd == 2 or synthesis_clarify:
        pieces.append(_synthesis_operational_instructions(phase=phase, feedback_round=rnd, synthesis_clarify=synthesis_clarify))
    elif rex:
        # 僅有心得節選、其餘皆預設：提醒納入考量即可
        pieces.append(
            "【回饋注意】學生另提供了上方「閱讀心得／摘記節選」；若與【整合草稿】有關，請一併考量是否呼應；"
            "若無關則不必硬扯。"
        )

    return "\n\n".join(p for p in pieces if p.strip())


def build_synthesis_coach_system_prompt(
    *,
    book_context: str,
    week1_orid_lines: dict[str, str],
    student_display_name: Optional[str] = None,
    student_login: Optional[str] = None,
    opening_hint: str = "",
    prev_ai_opener: Optional[str] = None,
    synthesis_phase: Optional[str] = None,
    feedback_round: int = 1,
    reading_excerpt: Optional[str] = None,
    synthesis_clarify: bool = False,
    student_text: str = "",
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
    mid = compose_synthesis_coach_mid_block(
        synthesis_phase=synthesis_phase,
        feedback_round=feedback_round,
        reading_excerpt=reading_excerpt,
        synthesis_clarify=synthesis_clarify,
        looks_pasted=looks_like_pasted_stage_paragraphs(student_text, week1_orid_lines),
    )
    return format_synthesis_coach_playbook(
        week1_block=joined,
        book_context=book_context,
        student_display_name=student_display_name,
        student_login=student_login,
        opening_hint=hint,
        prev_ai_opener=prev_ai_opener,
        synthesis_mid=mid,
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
        f"結構化回饋 JSON（含 rasf 白話、student_anchor_quote、draft_next_step、rag_context；請依 RASF-Anchor 規則組三段，第三段標題用「可以這樣修改：」）：\n{feedback_json_summary}"
    )
    return sys, user
