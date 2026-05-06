from __future__ import annotations

import re


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


_VAGUE_FEEDBACK_TOKENS = (
    "深化內容",
    "增加完整度",
    "內容完整度",
    "補充更多細節",
    "再完整一點",
    "更完整",
)

_CHILD_FRIENDLY_REPLACEMENTS = {
    "精準": "清楚",
    "精修": "修一下",
    "潤一下": "順一下",
    "成形": "比較完整",
    "站得住": "更有說服力",
    "可執行": "做得到",
    "骨架": "基本架構",
}


def _pick_phrase(options: tuple[str, ...], seed: str) -> str:
    if not options:
        return ""
    idx = sum(ord(c) for c in (seed or "")) % len(options)
    return options[idx]


def _stage_missing_pool(stage: str) -> tuple[str, ...]:
    s = (stage or "O").strip().upper()
    return {
        "O": (
            "還差一個具體事件：是誰做了什麼，先後順序怎麼走",
            "再補一句事件會更清楚：哪個人先做了哪個動作",
            "現在像在點到重點，還差一步：把「先發生、後發生」說出來",
        ),
        "R": (
            "還差一個感受和原因：你當下覺得什麼，為什麼會這樣覺得",
            "你有在回應故事了，再補一句「我覺得……因為……」會更完整",
            "感受有方向了，現在只差把原因連回故事那一幕",
        ),
        "I": (
            "還差一個想法和理由：你明白了什麼，故事裡哪一幕支持",
            "你的想法快成形了，再補一句「因為故事裡……」就會站得住",
            "這段重點是你學到什麼，還差一個故事證據來支持",
        ),
        "D": (
            "還差一個可做的第一步：下次在什麼情境，你會先做什麼",
            "行動方向有了，請再寫出「下次遇到……我會先……」",
            "這段要可執行，還差一個你真的做得到的第一步",
        ),
    }.get(s, ("還差一個明確主點，先補一句就好",))


def _stage_suggestion_pool(stage: str) -> tuple[str, ...]:
    s = (stage or "O").strip().upper()
    return {
        "O": (
            "試著寫：故事裡先發生的是……，後來……",
            "你可以這樣接：一開始……，接著……",
            "先用一句整理順序：先……再……",
        ),
        "R": (
            "試著寫：我覺得……，因為……",
            "你可以直接寫：我那時候覺得……，因為看到……",
            "先寫感受再寫原因：我會……，是因為……",
        ),
        "I": (
            "試著寫：這件事讓我明白……，因為……",
            "你可以寫成：我學到……，因為故事裡……",
            "先說你的提醒，再補根據：這提醒我……，因為……",
        ),
        "D": (
            "試著寫：下次遇到……，我會先……",
            "先寫第一步就好：下次我會先……，再……",
            "把行動寫小一點：當……的時候，我先……",
        ),
    }.get(s, ("試著先寫一句，再補一個小理由",))


def _draft_strength(stage: str, student_text: str) -> str:
    """
    Rough quality band for choosing tone:
    - low: very short / weakly structured
    - mid: has partial structure
    - high: already has stage-appropriate structure
    """
    s = (stage or "O").strip().upper()
    t = (student_text or "").strip()
    compact = re.sub(r"\s+", "", t)
    if len(compact) < 10:
        return "low"

    if s == "O":
        if any(k in t for k in ("一開始", "接著", "後來", "最後")) and len(compact) >= 18:
            return "high"
        if any(k in t for k in ("先", "後", "然後", "做了", "看到", "聽到")):
            return "mid"
        return "low"

    if s == "R":
        has_emo = any(k in t for k in ("開心", "難過", "生氣", "害怕", "擔心", "感動", "失望", "驚訝", "覺得", "感受"))
        has_reason = "因為" in t
        if has_emo and has_reason and len(compact) >= 14:
            return "high"
        if has_emo or has_reason:
            return "mid"
        return "low"

    if s == "I":
        has_claim = any(k in t for k in ("學到", "明白", "提醒", "道理", "意義", "價值", "我覺得"))
        has_reason = any(k in t for k in ("因為", "所以"))
        if has_claim and has_reason and len(compact) >= 14:
            return "high"
        if has_claim or has_reason:
            return "mid"
        return "low"

    has_action = any(k in t for k in ("下次", "我會", "先", "再", "打算", "步驟"))
    has_scene = any(k in t for k in ("遇到", "當", "如果", "時候"))
    if has_action and has_scene and len(compact) >= 14:
        return "high"
    if has_action:
        return "mid"
    return "low"


def detect_feedback_strength(stage: str, student_text: str) -> str:
    s = _draft_strength(stage, student_text)
    return s if s in {"low", "mid", "high"} else "mid"


def _child_friendly_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    for src, dst in _CHILD_FRIENDLY_REPLACEMENTS.items():
        t = t.replace(src, dst)
    return t


def _strength_prefix(stage: str, strength: str) -> str:
    s = (stage or "O").strip().upper()
    lv = (strength or "mid").strip().lower()
    mapping = {
        "low": {
            "O": "先把事件骨架搭起來就很棒了",
            "R": "先把感受說出來就有進步了",
            "I": "先把你的想法說出來就是關鍵一步",
            "D": "先寫出第一步行動就會清楚很多",
        },
        "mid": {
            "O": "方向對了，下一步把順序再講清楚",
            "R": "你有情緒方向了，再補原因就更完整",
            "I": "你有想法了，再補故事理由會更有力",
            "D": "你有行動方向了，再補場景就能直接做",
        },
        "high": {
            "O": "你已經抓到重點事件了，現在只要再精準一點",
            "R": "你的感受和原因都有了，再潤一下就很好",
            "I": "你的想法與理由已成形，再補一句會更穩",
            "D": "你的行動很具體了，再把第一步寫得更順",
        },
    }
    out = mapping.get(lv, mapping["mid"]).get(s, "方向是對的，我們再補一小步")
    return _child_friendly_text(out)


def normalize_feedback_focus(
    *,
    stage: str,
    missing: list[str],
    suggestions: list[str],
    student_text: str = "",
) -> tuple[list[str], list[str]]:
    """
    Make feedback actionable:
    - keep only one focus point
    - replace vague wording with stage-specific concrete phrasing
    """
    m0 = (missing[0] if missing else "").strip()
    s0 = (suggestions[0] if suggestions else "").strip()

    # Keep book-grounding correction untouched.
    if "對齊教材" in m0:
        if not s0:
            s0 = "請對照故事摘要，改用書中真實的人與事件重寫"
        return [m0], [s0]

    strength = _draft_strength(stage, student_text)
    seed = f"{stage}|{strength}|{student_text}|{m0}|{s0}"

    if (not m0) or any(tok in m0 for tok in _VAGUE_FEEDBACK_TOKENS):
        base = _pick_phrase(_stage_missing_pool(stage), seed)
        m0 = f"{_strength_prefix(stage, strength)}：{base}"

    if (not s0) or any(tok in s0 for tok in _VAGUE_FEEDBACK_TOKENS):
        s0 = _pick_phrase(_stage_suggestion_pool(stage), f"sug|{seed}")

    return [_child_friendly_text(m0)], [_child_friendly_text(s0)]


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
    missing, suggestions = normalize_feedback_focus(
        stage=stage,
        missing=missing,
        suggestions=suggestions,
        student_text=student_draft,
    )
    m0 = (missing[0] if missing else "").strip()
    s0 = (suggestions[0] if suggestions else "").strip()
    anchor = (book_anchor or "").strip()
    s_up = (stage or "O").strip().upper()
    nudge = ""
    if anchor:
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
        _grounding_praise_map = {
            "O": "你有試著寫出人物和事件，這是 O 段需要的方向；只是情節要再對回書裡。",
            "R": "你有試著寫出感受，這是 R 段需要的方向；只是原因要再連回書裡真的發生的事。",
            "I": "你有試著寫出想法，這是 I 段需要的方向；只是道理要再接回書裡真的發生的事。",
            "D": "你有試著寫出行動，這是 D 段需要的方向；只是可以再說說是受書中哪件事啟發的。",
        }
        line1 = _grounding_praise_map.get(s_up, "你有試著寫，我已經看到了；只是內容要再對回書裡。")
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
        _grounding_stem_map = {
            "O": "故事裡先發生的是……，後來……；請用書中真的人物和事件接下去。",
            "R": "我覺得……（書中角色）……，因為書裡發生了……，讓我有這個感受。",
            "I": "這件事讓我明白……，因為書裡的……告訴我……。",
            "D": "下次遇到……，我想到書裡……的故事，所以我會……。",
        }
        line3 = _grounding_stem_map.get(s_up, "故事裡先發生的是……，後來……；請用書中真的人物和事件接下去。")
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
