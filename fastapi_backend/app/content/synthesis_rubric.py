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


def lock_synthesis_content_for_grounding(levels: dict[str, Any] | None) -> dict[str, int]:
    """A material ambiguity or contradiction cannot earn content integration."""
    normalized = normalize_synthesis_levels(levels)
    normalized["content_integration"] = min(
        normalized.get("content_integration", 2),
        2,
    )
    return normalized


def synthesis_fallback_reply(focus: str | None) -> str:
    if focus is None:
        return (
            "你已經做到：\n你的文章已經把故事、想法、體會和行動清楚整合起來。\n"
            "再想一想：\n這次四個部分都已經完成，不需要再修改。\n"
            "可以這樣修改：\n可以保留現在的內容並儲存作品。"
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
