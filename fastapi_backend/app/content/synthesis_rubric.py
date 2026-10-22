"""Shared even-week integrated-writing rubric and badge mapping."""
from __future__ import annotations

import re
from typing import Any


SYNTHESIS_CRITERIA_ORDER = (
    "content_integration",
    "coherence",
    "reflection_depth",
    "action_application",
)

SYNTHESIS_BADGE_BY_CRITERION = {
    "content_integration": "badge_synthesis_content",
    "coherence": "badge_synthesis_coherence",
    "reflection_depth": "badge_synthesis_reflection",
    "action_application": "badge_synthesis_action",
}

SYNTHESIS_RUBRIC: dict[str, Any] = {
    "schema": "synthesis_rubric_v1",
    "version": 1,
    "pass_level": 3,
    "criteria": {
        "content_integration": {
            "name": "內容整合",
            "definition": "把具體故事事件、自己的感受或想法、體會與未來行動整合在文章中。",
            "levels": {
                1: "沒有明確故事內容、明顯離題，或只有零散句子。",
                2: "有提到故事或自己的想法，但感受、體會、行動有明顯缺漏，或彼此沒有關係。",
                3: "寫出具體故事事件，並包含自己的感受或想法、學到的體會及未來行動，各部分的關係可以理解。",
                4: "能選擇適合的故事情節支持自己的感受、體會和行動，全文圍繞一致的重點。",
            },
        },
        "coherence": {
            "name": "文章連貫",
            "definition": "內容順序合理，前後句與各部分之間能夠連接。",
            "levels": {
                1: "句子零散、互相矛盾，或難以理解主要意思。",
                2: "大致看得懂，但內容跳躍、重複，或只是把 ORID 四段直接貼在一起。",
                3: "內容順序合理，故事、感受、體會與行動之間的關係清楚，讀者能順利理解。",
                4: "前後銜接自然，能清楚呈現原因、結果或轉折，全文主題一致。",
            },
        },
        "reflection_depth": {
            "name": "反思深度",
            "definition": "超越故事重述，說明自己的感受、想法與學習原因。",
            "levels": {
                1: "只有重述故事，或只有簡單感想、口號。",
                2: "有寫感受或學到的道理，但原因模糊，沒有清楚連回故事。",
                3: "能用具體故事事件說明自己的感受、想法或學習原因。",
                4: "還能進一步思考角色立場、事情影響、自己的經驗，或更深一層的意義。",
            },
        },
        "action_application": {
            "name": "行動應用",
            "definition": "把體會轉化成自己實際可以做到的行動。",
            "levels": {
                1: "沒有提出自己的行動，行動明顯離題、不適當，或只寫別人應該怎麼做。",
                2: "有改善意願，但只有『我要努力、我要善良、我要幫助別人』等模糊方向。",
                3: "提出一個自己能做到、具體可行，而且能呼應故事體會的行動。",
                4: "還能說明實行情況、互動對象、做法、可能影響，或遇到困難時如何調整。",
            },
        },
    },
    "anchors": {
        "reflection_depth": {
            "level_2": "我覺得很難過，也學到要分享。",
            "level_3": "我看到故事人物最後失去珍惜的東西時覺得難過，因為他不願分享。",
        },
        "action_application": {
            "level_2": "以後我要幫助別人。",
            "level_3": "下次同學忘記帶彩色筆時，我會先問他需要哪一支，再借給他一起用。",
        },
    },
}


def parse_synthesis_level(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        level = int(value)
        return level if 1 <= level <= 4 else None
    match = re.search(r"\b([1-4])\b", str(value or ""))
    return int(match.group(1)) if match else None


def normalize_synthesis_levels(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    levels: dict[str, int] = {}
    for criterion in SYNTHESIS_CRITERIA_ORDER:
        level = parse_synthesis_level(raw.get(criterion))
        if level is not None:
            levels[criterion] = level
    return levels


def synthesis_badges_from_levels(levels: dict[str, Any] | None) -> list[str]:
    normalized = normalize_synthesis_levels(levels)
    return [
        SYNTHESIS_BADGE_BY_CRITERION[criterion]
        for criterion in SYNTHESIS_CRITERIA_ORDER
        if normalized.get(criterion, 0) >= int(SYNTHESIS_RUBRIC["pass_level"])
    ]


def first_synthesis_gap(levels: dict[str, Any] | None) -> str | None:
    normalized = normalize_synthesis_levels(levels)
    for criterion in SYNTHESIS_CRITERIA_ORDER:
        if normalized.get(criterion, 0) < int(SYNTHESIS_RUBRIC["pass_level"]):
            return criterion
    return None


_PASS_NEXT_STEP = "可以保留現在的內容並儲存作品。"
_PASS_DONE = "這次四個部分都已經完成，不需要再修改。"
_PASS_PRAISE = "你有把故事、自己的想法、體會和行動寫進這篇。"
_HEADINGS = (
    "你已經做到：",
    "你已經做到:",
    "再想一想：",
    "再想一想:",
    "可以這樣修改：",
    "可以這樣修改:",
    "本階段完成：",
    "本階段完成:",
    "下一步：",
    "下一步:",
)
_REVISION_HINTS = ("再補", "請回到", "還沒", "還可以補", "再修改", "先修改", "補上一")
_DONE_HINTS = ("不需要", "不用再", "已經完成", "已完成", "都完成", "可以了")
_SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?")


def _statement_sentences(text: str) -> list[str]:
    body = text or ""
    for heading in _HEADINGS:
        body = body.replace(heading, "\n")
    sentences: list[str] = []
    for match in _SENTENCE_RE.finditer(body):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        if sentence.endswith(("？", "?", "嗎")) or "嗎？" in sentence or "嗎?" in sentence:
            continue
        if any(hint in sentence for hint in _REVISION_HINTS):
            continue
        if sentence.strip("。！ ") == _PASS_NEXT_STEP.strip("。"):
            continue
        if not sentence.endswith(("。", "！")):
            sentence = f"{sentence}。"
        sentences.append(sentence)
    return sentences


def format_synthesis_pass_reply(model_reply: str | None) -> str:
    """Turn a passed synthesis reply into an affirmation, with no revision questions."""
    praise: list[str] = []
    done: list[str] = []
    for sentence in _statement_sentences(model_reply or ""):
        if any(hint in sentence for hint in _DONE_HINTS):
            done.append(sentence)
        else:
            praise.append(sentence)
    praise_text = "".join(praise) or _PASS_PRAISE
    done_text = "".join(done) or _PASS_DONE
    return (
        f"你已經做到：\n{praise_text}\n\n"
        f"本階段完成：\n{done_text}\n\n"
        f"下一步：\n{_PASS_NEXT_STEP}"
    )


_MISMATCH_SAID_CUES = (
    "不太一樣",
    "不一樣",
    "對不上",
    "故事裡沒有",
    "書裡沒有",
    "不在書",
    "不是這樣",
    "跟故事裡",
    "和故事",
    "跟書",
    "和書",
)


def _reply_already_names_mismatch(text: str, span: str) -> bool:
    """Keep the model's own wording when it already points at this sentence."""
    if not any(cue in text for cue in _MISMATCH_SAID_CUES):
        return False
    if not span:
        return False
    if span in text:
        return True
    window = 6 if len(span) >= 6 else len(span)
    return any(span[i : i + window] in text for i in range(0, len(span) - window + 1))


def ensure_synthesis_mismatch_reply(model_reply: str | None, quote: str) -> str:
    """Keep the model's sentences when they already name the mismatch.

    A fixed card is only the backup for a reply that never says the sentence
    differs from the story.
    """
    span = (quote or "").strip()
    text = (model_reply or "").strip()
    if not span:
        return text
    if text and _reply_already_names_mismatch(text, span):
        return text
    praise = ""
    marker = "你已經做到："
    if marker in text:
        rest = text.split(marker, 1)[1]
        for heading in ("再想一想：", "可以這樣修改：", "本階段完成：", "下一步："):
            if heading in rest:
                rest = rest.split(heading, 1)[0]
        praise = "".join(
            sentence
            for sentence in _statement_sentences(rest)
            if span in sentence or "你寫" in sentence
        )
    if not praise:
        praise = f"你寫到「{span}」。"
    return (
        f"你已經做到：\n{praise}\n\n"
        f"再想一想：\n你寫的「{span}」，跟故事裡發生的不太一樣喔。\n\n"
        "可以這樣修改：\n你再想想看，故事裡發生的是哪一件事呢？用你自己的話，把這一句改一改就好。"
    )


def _looks_like_pass_card(text: str) -> bool:
    """A completion card still has a gap when the shared action gate lowers a level."""
    if "再想一想" in (text or ""):
        return False
    return "本階段完成" in (text or "")


def synthesis_visible_reply(model_reply: str | None, focus: str | None) -> str:
    """Show the model's own sentences. A passed piece is affirmed instead of questioned."""
    text = (model_reply or "").strip()
    if focus is None:
        if not text:
            text = synthesis_fallback_reply(None)
        return format_synthesis_pass_reply(text)
    if text and not _looks_like_pass_card(text):
        return text
    return synthesis_fallback_reply(focus)


def synthesis_fallback_reply(focus: str | None) -> str:
    if focus is None:
        return (
            "你已經做到：\n你的文章已經把故事、想法、體會和行動清楚整合起來。\n\n"
            "本階段完成：\n這次四個部分都已經完成，不需要再修改。\n\n"
            "下一步：\n可以保留現在的內容並儲存作品。"
        )
    guidance = {
        "content_integration": (
            "你已經寫下了一些和故事有關的內容。",
            "現在還要讓故事事件、你的想法、學到的事和行動彼此有關。",
            "故事裡哪一件事讓你有這個想法？你可以在原句前後補上一句。",
        ),
        "coherence": (
            "你的文章已經有可以繼續整理的內容。",
            "有兩個部分接得比較突然，讀者不容易看出它們的關係。",
            "找出跳得最快的兩句，中間補一句『看到這件事，我……』來連接。",
        ),
        "reflection_depth": (
            "你已經寫出自己的感受或學到的事。",
            "現在還少了你為什麼會這樣想的原因。",
            "故事裡哪一個畫面讓你有這個感受或體會？為什麼？",
        ),
        "action_application": (
            "你已經寫出未來想努力的方向。",
            "現在還要把方向變成自己真的做得到的行動。",
            "下次遇到什麼情況時，你會先做哪一件事？",
        ),
    }
    praise, missing, question = guidance.get(focus, guidance["content_integration"])
    return (
        f"你已經做到：\n{praise}\n"
        f"再想一想：\n{missing}\n"
        f"可以這樣修改：\n{question}"
    )
