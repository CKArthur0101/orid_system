from __future__ import annotations


def stage_name_zh(stage: str) -> str:
    s = (stage or "O").strip().upper()
    return {"O": "客觀", "R": "感受", "I": "意義", "D": "行動"}.get(s, "這一段")


def stage_focus_line(stage: str) -> str:
    s = (stage or "O").strip().upper()
    return {
        "O": "O：只談故事裡「發生什麼、先後順序、誰做了什麼」，不要帶進大道理或行動。",
        "R": "R：只談「心情／感受」並用「因為…」連回故事中的某一幕，不要改寫成整篇大意。",
        "I": "I：只談「這代表什麼、提醒了什麼」並用故事細節當理由，不要空喊口號。",
        "D": "D：只談「下次我會做的一個具體小步驟」，要寫得出場景或時機，不要只有決心句。",
    }.get(s, "")
