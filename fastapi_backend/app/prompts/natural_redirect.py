from __future__ import annotations

from typing import Literal

from .shared import build_book_context_block

RedirectCategory = Literal["unsafe", "off_topic", "low_effort", "meta", "rate_limit", "factual_mismatch", "fallback"]

_CATEGORY_POLICY = {
    "unsafe": "用一句簡短界線，提醒先用不傷人的語氣，不重複原本不當詞。",
    "off_topic": "輕微承接即可，不展開生活話題，立即拉回閱讀內容。",
    "low_effort": "不要責備；用好奇和支持語氣，引導學生多補一點。",
    "meta": "只用一句極短身分或規則說明，不談系統細節。",
    "rate_limit": "語氣溫和提醒慢一點，避免像警告。",
    "factual_mismatch": "先溫和對齊故事事實，不否定學生，再拉回剛剛正在問的問題。",
    "fallback": "自然接住學生訊息，然後回到閱讀任務。",
}


def build_natural_redirect_prompt(
    *,
    category: RedirectCategory,
    stage: str,
    student_text: str,
    fallback_question: str,
    book_pack: dict | None,
    strike_count: int = 1,
) -> str:
    stage = (stage or "O").strip().upper()
    if stage not in {"O", "R", "I", "D"}:
        stage = "O"
    category = category if category in _CATEGORY_POLICY else "fallback"
    strike_count = max(1, int(strike_count or 1))
    tone_level = "溫和" if strike_count <= 2 else "較堅定但尊重"
    book_context = build_book_context_block(book_pack, max_events=6, max_chars=1100)

    return f"""
<角色設定>
你是自然、尊重學生的國小閱讀助教。
任務是生成「兩句」學生可見回覆，不要列點。
</角色設定>

<輸出語言>
兩句都必須是台灣繁體中文（正體字），禁止使用簡體中文。
</輸出語言>

<情境>
分類：{category}
目前階段：{stage}
連續次數：{strike_count}
語氣強度：{tone_level}
策略：{_CATEGORY_POLICY[category]}
</情境>

<輸出規則>
1) 只輸出兩句。
2) 第一句：自然接住或溫和糾偏，不責備、不羞辱。
3) 第二句：只能有一個問號，且要回到書中角色、事件或場景。
4) 不要使用這些詞：系統、階段、ORID、檢測到、違規、規則引擎。
5) 不要逐字重複 fallback_question，請改寫成口語問法。
6) 若 category=unsafe，不得重複學生不當原句。
7) 若 category=factual_mismatch，第一句要清楚說「書裡沒有這段」或「這本書沒有這件事」。
</輸出規則>

<參考問題方向>
不可照抄：{fallback_question}
</參考問題方向>

<教材資訊>
{book_context}
</教材資訊>

<學生訊息>
{student_text}
</學生訊息>
""".strip()
