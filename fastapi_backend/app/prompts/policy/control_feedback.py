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
    return f"你有寫到「{one}」，我有看到你正在寫「{stage_zh}」這一段，方向是對的。"


def _is_generic_praise(p: str) -> bool:
    p = (p or "").strip()
    if not p:
        return True
    if "先把想法寫在紙上" in p:
        return True
    if "有寫到重點" in p and "不錯喔" in p and "你「" in p:
        return True
    return False


def _default_example_line(stage: str, anchor: str = "") -> str:
    s = (stage or "O").strip().upper()
    a = (anchor or "").strip()
    if s == "O":
        if a:
            return f"例如：一開始「{a}」，後來又發生了別的事，你可以把後面那一句接著寫出來。"
        return "例如：一開始……，後來……。先把前後順序寫出來就可以了。"
    if s == "R":
        if a:
            return f"例如：我看到「{a}」這一幕時，覺得有點難過，因為我覺得他沒有想到別人。"
        return "例如：我覺得……，因為……。先寫感受，再補原因。"
    if s == "I":
        if a:
            return f"例如：這件事讓我明白不能只想到自己，因為「{a}」讓我看到分享很重要。"
        return "例如：這件事讓我明白……，因為……。先寫你學到什麼，再補理由。"
    if a:
        return f"例如：下次遇到像「{a}」這樣的情況，我會先停一下，再想想要怎麼做比較好。"
    return "例如：下次遇到……，我會先……。先寫你做得到的第一步就好。"


def format_control_feedback_reply(
    *,
    ok: bool,
    missing: list[str],
    suggestions: list[str],
    stage: str,
    book_anchor: str = "",
    example: str | None = None,
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
            nudge = f"我們先看「{anchor}」這件事，先寫一開始發生什麼，再寫後來怎麼了。"
        elif s_up == "R":
            nudge = f"我們先想想「{anchor}」這一幕讓你有什麼感覺，再用「我覺得……，因為……」接著寫。"
        elif s_up == "I":
            nudge = f"我們先用「{anchor}」這件事想一想，你從這裡學到什麼，再補一句理由就可以。"
        else:
            nudge = f"我們先想成「{anchor}」那種情況，你下次第一步可以做什麼小行動？"

    pr = (praise or "").strip()
    if "對齊教材" in m0:
        grounding_praise_map = {
            "O": "你有試著寫出人物和事情，這個方向是對的；我們再把內容對回書裡就更好了。",
            "R": "你有試著寫出感受，這個方向是對的；我們再把原因接回書裡真的發生的事。",
            "I": "你有試著寫出自己的想法，這個方向是對的；我們再把理由接回書裡真的發生的事。",
            "D": "你有試著寫出自己的行動，這個方向是對的；我們再想想這和書裡哪件事有關。",
        }
        line1 = grounding_praise_map.get(s_up, "你有試著寫，我已經看到了；只是內容要再對回書裡。")
    elif _is_generic_praise(pr) and (student_draft or "").strip():
        line1 = _praise_line_from_draft(student_draft, stage)
    elif pr and not _is_generic_praise(pr):
        line1 = pr
    else:
        line1 = _praise_line_from_draft(student_draft, stage) if (student_draft or "").strip() else (pr or "你有試著寫，我已經看到了。")

    if ok:
        line2 = m0 if m0 else "如果你想讓這段更清楚，我們只要再補一個小地方就好。"
    else:
        line2 = m0 if m0 else "我們先只改一個地方，這段就會更清楚。"

    if s0 and "用。結尾" in s0:
        base_line3 = "我們一步一步來，先把同一件事寫成完整一句，再加上句號；先寫誰做了什麼，再補後來怎樣。"
    elif "對齊教材" in m0:
        grounding_stem_map = {
            "O": "我們先對回書中真的人物和事情，再按順序把前面和後面寫清楚，不要只寫最後一小段。",
            "R": "我們先對回書裡真的情節，再把你的感受和原因接在同一句裡。",
            "I": "我們先對回書裡真的情節，再寫你明白了什麼，然後補一個故事理由。",
            "D": "我們先想想書裡帶給你的提醒，再把你下次會做的行動寫清楚。",
        }
        base_line3 = grounding_stem_map.get(s_up, "我們先對回書裡真的人物和事情，再照順序把內容寫清楚。")
    elif s0 and not any(
        x in s0 for x in ("補充更多細節", "內容完整度", "深化內容", "增加完整度")
    ):
        base_line3 = f"我們一步一步來，{s0}"
    elif nudge:
        base_line3 = nudge
    else:
        base_line3 = "我們先補一個最重要的地方就好，寫成 1 到 2 句，讓讀的人一下就看懂你在說什麼。"

    ex = (example or "").strip() or _default_example_line(stage, anchor)
    if ex.startswith("例如："):
        line3 = f"{base_line3}\n{ex}"
    else:
        line3 = f"{base_line3}\n例如：{ex}"

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
