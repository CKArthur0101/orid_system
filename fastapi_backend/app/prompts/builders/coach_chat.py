from __future__ import annotations

import re
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

_COHERENCE_FORCE_REPLY = (
    "本輪回饋請優先只看「連貫性」這一項："
    "先肯定四個部分都在了，只針對上面標出的那個交界處（若沒有標出，你自己找全文中最跳的一處）"
    "指出可以加一句銜接、並給一個銜接語或連接詞的小範例即可；"
    "**不要**要求整篇重寫、**不要**要求把每一段都改寫、"
    "**不要**去改『行動』那一句本身的長短或拆句——連貫的重點是段落之間有沒有橋，不是句子本身寫得好不好。"
    "**不要**說「串起來了」「接得很順」「整篇很完整就好」；"
    "本輪先不要談 SEL 表現或行動精修；等銜接補上後，下一輪再考慮。"
)

# Generic reflective-writing cues — deliberately book-agnostic (no character/plot
# nouns) so this generalises across every book pack, not just one sample essay.
_O_CUE = re.compile(r"(故事[裡里中]|書[裡裏]|文章[裡裏]|繪本[裡裏]|一開始|主角|作者)")
_R_CUE = re.compile(r"(我覺得|我感到|讓我覺得|覺得很|心情|很難過|很生氣|很開心|很感動|很孤單|很小氣|很害怕)")
_I_CUE = re.compile(r"(學到|讓我學到|想到|明白|道理|提醒我|原來|懂了|體會到)")
_D_CUE = re.compile(r"(下次|以後|我會|如果.{0,10}(遇到|發生)|打算)")

# Generic connective phrases that mark a *deliberate* transition between stages —
# their absence around a boundary (not merely anywhere in the essay) is the signal.
_GLUE_CONNECTORS = re.compile(
    r"(因此|於是|這讓我聯想|同樣地|就像|舉例來說|換句話說|進一步|讀完之後|"
    r"從這件事|所以下次|因為這樣|我才明白|這讓我覺得|後來看到|也讓我|讓我想到|"
    r"這也讓|因為這件事|正因為)"
)

_BOUNDARY_ZH = {"O_R": "故事→感受", "R_I": "感受→體會", "I_D": "體會→行動"}


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


def _first_match_after(pattern: re.Pattern[str], t: str, after: int) -> Optional[re.Match[str]]:
    for m in pattern.finditer(t):
        if m.start() >= after:
            return m
    return None


def find_abrupt_orid_boundaries(text: str) -> list[str]:
    """Return which O→R / R→I / I→D transitions lack a nearby connective phrase.

    Checks connector presence *around each specific boundary* rather than
    counting glue words anywhere in the essay — a connector used near one
    boundary shouldn't hide a genuinely abrupt jump elsewhere, and a draft
    with no book-specific keywords (any book pack) can still be detected.
    """
    t = re.sub(r"\s+", "", (text or "").strip())
    if len(t) < 48:
        return []

    o = _first_match_after(_O_CUE, t, 0)
    if not o:
        return []
    r = _first_match_after(_R_CUE, t, o.end())
    if not r:
        return []
    i = _first_match_after(_I_CUE, t, r.end())
    if not i:
        return []
    d = _first_match_after(_D_CUE, t, i.end())
    if not d:
        return []

    def _has_glue(a: int, b: int) -> bool:
        lo, hi = max(0, a - 6), min(len(t), b + 6)
        return bool(_GLUE_CONNECTORS.search(t[lo:hi]))

    abrupt: list[str] = []
    if not _has_glue(o.start(), r.start()):
        abrupt.append("O_R")
    if not _has_glue(r.start(), i.start()):
        abrupt.append("R_I")
    if not _has_glue(i.start(), d.start()):
        abrupt.append("I_D")
    return abrupt


def looks_like_hard_stitched_orid_synthesis(text: str) -> bool:
    """True when a synthesis draft still reads like O→R→I→D hard-stitched stages.

    Completeness can be fine while coherence is weak: story cue, then feeling,
    then lesson, then future action appear in order, with at least two of the
    three transitions missing any connective phrase nearby.
    """
    return len(find_abrupt_orid_boundaries(text)) >= 2


def _coherence_priority_mid_block(*, kind: str, abrupt_boundaries: Optional[list[str]] = None) -> str:
    if kind == "pasted":
        head = (
            "【偵測】草稿看起來像是把上週幾段（觀察／感受／體會／行動）直接貼上、"
            "段落之間還沒加銜接語。這種情況通常代表「完整性」已經有了；"
        )
    else:
        boundary_hint = ""
        if abrupt_boundaries:
            zh = "、".join(_BOUNDARY_ZH.get(b, b) for b in abrupt_boundaries)
            boundary_hint = f"銜接特別不足的地方大約在「{zh}」之間；"
        head = (
            "【偵測】草稿雖然故事／感受／體會／行動大致都有，但讀起來仍像把四格"
            f"一段接一段硬串，銜接還不夠（完整 ≠ 連貫）。{boundary_hint}"
        )
    return head + _COHERENCE_FORCE_REPLY


_SYNTHESIS_RUBRICS: tuple[tuple[str, str], ...] = (
    ("完整性", "文章是否包含故事事件、感受、體會與未來行動四個部分？"),
    ("連貫性", "句子之間是否順暢？不是把四段硬貼在一起，而是有串接。"),
    ("反思深度", "是否說明原因、想法、體會，並能從故事連結到自己的生活經驗？"),
    (
        "SEL表現",
        "是否看得出情緒覺察、同理、關係理解或負責任行動？（引導用，勿對學生說 SEL 術語）",
    ),
    ("行動具體性", "D 的部分是否具體？學生是否說出實際能做到的行動？"),
)


def _synthesis_phase_zh(phase: str) -> str:
    return {
        "select_evidence": "階段 A：選證據／帶材料",
        "align_prompt": "階段 B：對齊題幹（鷹架句）",
        "short_draft": "階段 C：短初稿",
        "expand_revise": "階段 D：擴寫／修訂",
    }.get(phase, phase)


def _depth_priority_mid_block() -> str:
    """Round-2 guidance when coherence gaps are no longer the main issue."""
    return (
        "【第二輪／銜接已大致足夠】"
        "學生已用過第一輪整合回饋，草稿銜接問題已大致處理或不再明顯；"
        "本輪**不要**再談段落銜接、**不要**要求改短／拆句／重寫最後一句行動。"
        "本輪只挑一個主缺口，優先順序：反思深度（原因、生活連結）→ "
        "SEL 表現（一個短問，勿說術語）→ 行動具體性（何時、對誰、怎麼開口，"
        "不是句子長短）。若行動已有明確場景，改問「會先對對方說什麼」"
        "或「這個行動跟剛才學到的道理怎麼連」，不要叫拆成兩句短句。"
    )


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
        lines.append(
            "【本輪為第二輪】銜接若已大致足夠，本輪**不要**再談連貫或改句子長短；"
            "在反思深度、SEL 表現（一個短問句）與行動具體性中只挑一個主缺口，"
            "仍以短段落、不要代寫全文。"
        )
        lines.append(
            "【本輪檢查重點（對照下列 1～2 條即可）】\n"
            "- 反思深度：是否說明感受原因、體會，並能連結到自己的真實生活經驗？\n"
            "- SEL 表現：情緒覺察、同理、關係理解或負責任行動擇一短問（勿說 SEL）。\n"
            "- 行動具體性：是否說出何時、對誰、會怎麼開口或怎麼做？（不是把句子改短）"
        )

    if r1:
        lines.append(
            "【兩輪制／份量】這是**第一輪**：請**只給「一個」最小下一步**（一句方向 + 可選半句示例提示），"
            "不要一次列很多缺點、不要代寫整段；請學生回到整合格子自己改。"
        )
    else:
        lines.append(
            "【兩輪制／份量】這是**第二輪**：在反思深度、SEL 或行動具體性上再多一小層，"
            "仍請維持短段落，不要代寫整篇；**不要**回頭改短最後一句或談銜接。"
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
        return (
            "反思深度與 SEL 表現：原因／生活連結是否清楚？必要時一個短問補強情緒覺察或同理。",
            frozenset({"反思深度", "SEL表現"}),
        )
    # expand_revise
    if not r2:
        return (
            "反思深度、SEL 表現與行動具體性：體會是否清楚？行動是否具體可做？",
            frozenset({"反思深度", "行動具體性", "SEL表現"}),
        )
    return (
        "行動具體性為主；若行動已具體，可給一個負責任行動／關係理解的短問。",
        frozenset({"行動具體性", "SEL表現"}),
    )


def compose_synthesis_coach_mid_block(
    *,
    synthesis_phase: Optional[str],
    feedback_round: int,
    reading_excerpt: Optional[str],
    synthesis_clarify: bool,
    looks_pasted: bool = False,
    hard_stitched_boundaries: Optional[list[str]] = None,
) -> str:
    """
    Inserted between 【教材脈絡】 and personal tail.
    Empty when legacy defaults (round 1, no phase, no excerpt, no clarify).
    """
    pieces: list[str] = []
    rnd = 2 if int(feedback_round) == 2 else 1
    rex = (reading_excerpt or "").strip()
    if rex:
        cap = rex[:2000]
        tail_note = "\n（以上節選已截斷至約 2000 字）" if len(rex) > 2000 else ""
        pieces.append(f"【學生自填閱讀心得／摘記節選（唯讀）】\n{cap}{tail_note}")

    if looks_pasted:
        pieces.append(_coherence_priority_mid_block(kind="pasted"))
    elif hard_stitched_boundaries:
        pieces.append(_coherence_priority_mid_block(kind="hard_stitched", abrupt_boundaries=hard_stitched_boundaries))
    elif rnd == 2:
        pieces.append(_depth_priority_mid_block())

    phase = synthesis_phase if (synthesis_phase or "") in _SYNTHESIS_PHASE_CHOICES else None

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
    pasted = looks_like_pasted_stage_paragraphs(student_text, week1_orid_lines)
    abrupt_boundaries = [] if pasted else find_abrupt_orid_boundaries(student_text)
    hard_stitched_boundaries = abrupt_boundaries if len(abrupt_boundaries) >= 2 else []
    mid = compose_synthesis_coach_mid_block(
        synthesis_phase=synthesis_phase,
        feedback_round=feedback_round,
        reading_excerpt=reading_excerpt,
        synthesis_clarify=synthesis_clarify,
        looks_pasted=pasted,
        hard_stitched_boundaries=hard_stitched_boundaries,
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
