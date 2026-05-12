from __future__ import annotations

from app.prompts.policy.feedback_focus import normalize_feedback_focus
from app.prompts.shared_parts.stage_text import stage_name_zh


def _praise_line_from_draft(t: str, stage: str) -> str:
    """從學生草稿截一小段用於稱讚，避免全篇罐頭句（無 LLM 或 praise 不具體時）。"""
    t = (t or "").strip()
    s = (stage or "O").strip().upper()
    stage_zh = stage_name_zh(s)
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
        grounding_praise_map = {
            "O": "你有試著寫出人物和事件，這是 O 段需要的方向；只是情節要再對回書裡。",
            "R": "你有試著寫出感受，這是 R 段需要的方向；只是原因要再連回書裡真的發生的事。",
            "I": "你有試著寫出想法，這是 I 段需要的方向；只是道理要再接回書裡真的發生的事。",
            "D": "你有試著寫出行動，這是 D 段需要的方向；只是可以再說說是受書中哪件事啟發的。",
        }
        line1 = grounding_praise_map.get(s_up, "你有試著寫，我已經看到了；只是內容要再對回書裡。")
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
        grounding_stem_map = {
            "O": "故事裡先發生的是……，後來……；請用書中真的人物和事件接下去。",
            "R": "我覺得……（書中角色）……，因為書裡發生了……，讓我有這個感受。",
            "I": "這件事讓我明白……，因為書裡的……告訴我……。",
            "D": "下次遇到……，我想到書裡……的故事，所以我會……。",
        }
        line3 = grounding_stem_map.get(s_up, "故事裡先發生的是……，後來……；請用書中真的人物和事件接下去。")
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
        f"我有看到你的訊息。關於{stage_name_zh(stage)}這一段，建議你對照教材裡的事件，"
        "把草稿寫具體一點；需要結構化建議時，可以按該格的「取得回饋」。"
    )
