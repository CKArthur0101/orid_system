"""
Stable phrase pools per input bucket; pick_variant is deterministic from seed.
"""

from __future__ import annotations

import hashlib
from typing import Final

from app.prompts.policy.student_input_bucket import (
    BUCKET_EMPTY,
    BUCKET_LATIN_HEAVY,
    BUCKET_LIKELY_GIBBERISH,
    BUCKET_MIXED_SCRIPT,
    BUCKET_NORMAL,
    BUCKET_TOO_SHORT,
)

_VARIANTS: Final[dict[str, list[str]]] = {
    BUCKET_NORMAL: [
        "先把你最在意的一句寫滿，再往回補細節。",
        "這一輪我們只鎖一個小目標，寫完再往下。",
        "你可以先照順序把「誰／做了什麼」說清楚。",
        "想到哪就寫哪一句，我們再一起把它變完整。",
        "先寫一個你記得最清楚的畫面。",
        "用一句話把心情釘在故事裡的某個點上。",
        "先別急著漂亮，先把事實講完整。",
        "挑一個詞當錨點，圍著它多寫半句。",
        "寫完一句就停一下，看看讀者會不會懂。",
        "把「因為」或「所以」其中一個補出來就好。",
        "先回答：這件事跟你有什麼連結？",
        "用你剛剛那句話當開頭，往後接一小步。",
    ],
    BUCKET_TOO_SHORT: [
        "再多半句就好：誰或什麼讓你有這個感覺？",
        "試著把畫面補一個詞：地點、人物或動作擇一。",
        "你可以多寫「因為……」讓讀者跟上。",
        "加一個具體例子，哪怕只有五個字。",
        "把時間點說出來：先／後／最後擇一。",
        "用一句話回答：你現在最想被看懂的是什麼？",
        "補上你心裡的那個「所以」。",
        "多寫一個動詞，讀者會更跟得上。",
        "把感受跟故事裡的一件事扣在一起。",
        "寫完再讀一次，看看有沒有主詞。",
    ],
    BUCKET_LIKELY_GIBBERISH: [
        "慢慢來，用一句完整話告訴我你想說的重點。",
        "你可以照順序打：先發生什麼，再來呢？",
        "試著用十個字以上描述一個畫面。",
        "先寫一個真實的句子，我們再一起調整。",
        "把鍵盤放慢一點，像跟同學講話那樣寫。",
        "用「我看到／我覺得」其中一個開頭試試。",
        "先說故事裡的一個人名，再接一句話。",
        "不用一次寫很多，一句就好。",
        "把你想問老師的事用完整句寫出來。",
        "若剛剛是誤觸，重新貼一次你想被看的內容。",
    ],
    BUCKET_LATIN_HEAVY: [
        "Write one more concrete detail (who/what/when) in your next line.",
        "Pick one story moment and add a feeling word.",
        "Connect your idea to one event from the book in plain words.",
        "Add a short 'because …' to help the reader follow.",
        "Turn your last sentence into a small step forward.",
        "If mixed languages, keep your main language steady for two sentences.",
        "Name one character from the book, then say what they did.",
        "End with one question you could answer next.",
    ],
    BUCKET_MIXED_SCRIPT: [
        "這一輪請選一種主要語言寫兩句，另一種最多補一句。",
        "先用你最順的語言把意思寫完整，再決定要不要翻譯。",
        "中英混用時，把故事人名統一成書上用法。",
        "先固定語氣：全繁中或全英文擇一寫一小段。",
        "把關鍵名詞用同一語言寫兩次，讀者較不會迷路。",
        "用繁中寫感受、用英文寫動作也可以，但要各有一句完整。",
        "選一個句子當『主語言』，其餘當補充。",
        "先寫完意思，我們再一起整理用詞。",
    ],
    BUCKET_EMPTY: [
        "先貼上一句你想被看的草稿，我們從那裡開始。",
        "寫一個詞或半句也可以，當作起頭。",
        "從故事裡你記得的一個畫面寫起。",
        "先打一句心情，再補故事連結。",
        "把課文裡一句話抄下來當錨點也行。",
    ],
}


def pick_variant(seed: str, bucket: str) -> str:
    pool = _VARIANTS.get(bucket) or _VARIANTS[BUCKET_NORMAL]
    h = hashlib.sha256((seed or "").encode("utf-8")).hexdigest()
    idx = int(h[:12], 16) % len(pool)
    return pool[idx]
