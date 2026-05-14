from __future__ import annotations

import re

# Control path: paired missing/suggestion for O「卡在誰做了什麼」
CONTROL_O_META_MISSING = "內容還有點短，讀的人還看不出故事在演什麼。"
CONTROL_O_META_SUGGESTION = "我們先補一句「是誰做了什麼」，事情就會更清楚。"

# GenAI normalize: replace canned O missing when student is meta-stuck and model missing is generic
GENAI_META_MISSING_FALLBACK = (
    "你現在卡在「想故事裡誰做了什麼」；我們先用故事摘要的一句「誰做了什麼」接寫就好。"
)

_BRACKET_PREFIX = re.compile(r"^\s*\[[^\]]+\]\s*")


def strip_orid_stage_tag(text: str) -> str:
    """Remove leading [O 本段寫作] 等標籤，供長度與內容判斷。"""
    t = (text or "").strip()
    t = _BRACKET_PREFIX.sub("", t).strip()
    return t


def student_o_meta_stuck(text: str) -> bool:
    """學生在 O 段卡在「想不出書裡誰做了什麼」等 meta 句，而非具體事件草稿。"""
    core = strip_orid_stage_tag(text).replace(" ", "").replace("\n", "")
    if not core:
        return True
    if len(core) < 10:
        return True
    meta = (
        "不知道誰",
        "不知道在寫",
        "不知道要寫",
        "不知道寫",
        "不知道該",
        "誰做了什麼",
        "要寫什麼",
        "怎麼寫",
        "還不會寫",
        "不會寫",
        "好難寫",
        "一片空白",
        "腦袋空白",
    )
    if any(m in core for m in meta):
        return True
    # 只有泛問句、幾乎沒有事件詞
    if len(core) < 24 and not any(
        k in core for k in ("爺", "柿", "藏", "倉庫", "奶奶", "同學", "一開始", "最後", "然後", "把", "給")
    ):
        if any(k in core for k in ("不知道", "不會", "怎麼", "什麼", "誰")):
            return True
    return False


def is_o_placeholder_or_stuck_draft(text: str) -> bool:
    """O 段取得回饋：極短或罐頭／卡住草稿，優先用書本錨點而非範例句。"""
    core = strip_orid_stage_tag(text).replace(" ", "").replace("\n", "")
    if not core:
        return True
    if len(core) < 8:
        return True
    if student_o_meta_stuck(text):
        return True
    if len(core) < 36 and re.fullmatch(r"[好嗯喔哦欸耶啊哈]+[，。、]?不知道[。…]*", core):
        return True
    return False


def personalized_control_praise_line(draft: str, stage_zh: str) -> str:
    """控制組稱讚：若草稿已有具體名詞／事件，回一句貼稿的短稱讚，否則空字串。"""
    core = strip_orid_stage_tag(draft).replace("\n", " ").strip()
    if len(core) < 6:
        return ""
    concrete = any(
        k in core
        for k in (
            "阿松",
            "爺爺",
            "柿子",
            "倉庫",
            "奶奶",
            "同學",
            "陀螺",
            "樹枝",
            "葉",
            "藏",
            "分",
            "哎唷",
        )
    )
    if not concrete:
        return ""
    snippet = core
    for sep in ("。", "！", "？", "，"):
        if sep in snippet:
            snippet = snippet.split(sep, 1)[0].strip()
            break
    if len(snippet) > 40:
        snippet = snippet[:37] + "…"
    return f"你有試著寫到「{snippet}」，我有看到你在寫「{stage_zh}」這一段。"
