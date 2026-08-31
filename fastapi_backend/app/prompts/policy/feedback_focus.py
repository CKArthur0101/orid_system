from __future__ import annotations

import re

from app.prompts.policy.turn_destination import GENAI_META_MISSING_FALLBACK, student_o_meta_stuck


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
    "支持": "說明",
    "主點": "重點",
}


def _pick_phrase(options: tuple[str, ...], seed: str) -> str:
    if not options:
        return ""
    idx = sum(ord(c) for c in (seed or "")) % len(options)
    return options[idx]


def _missing_options(stage: str, strength: str) -> tuple[str, ...]:
    """Progressive hints: stronger drafts get 'next rung' asks, not repeats of basics."""
    s = (stage or "O").strip().upper()
    lv = (strength or "mid").strip().lower()
    if s == "O":
        if lv == "high":
            return (
                "想一想書裡接下來還發生什麼：若還有一句**比較大的情節**幾乎沒出現在你寫的稿子裡，請先把那一句用你自己的話補進 O（可先寫一句接在合適的位置）。",
                "目前幾件事寫得很清楚；下一步試著寫出**故事裡還沒提到的一段**（例如中間衝突或轉變），先用一段話串一個重點就好。",
                "若書裡重點情節你都已經有寫到，再挑一個：補一句更細的動作、或補一句旁人反應（二選一）。",
            )
        if lv == "mid":
            return (
                "方向對了，下一步把先後再銜接一句：讓讀者跟上誰先做了什麼",
                "你有把重點寫出來了，下一步補一句「接著又發生什麼」讓故事更連貫",
                "下一步試著多寫一句：事情是在哪裡發生的（仍然是客觀描述）",
            )
        return (
            "還差一個清楚的事件：是誰做了什麼，事情先後怎麼發生",
            "再補一句事件會更清楚：哪個人先做了哪個動作，後來又怎麼了",
            "你有把一點點重點寫出來了，下一步把「誰」跟「做了什麼」寫滿一句",
        )
    if s == "R":
        if lv == "high":
            return (
                "感受跟原因都上路了，下一步把感受寫具體一點：哪一個畫面讓你最有感",
                "你已經連到故事了，下一步試著多說一句「那時候我心裡像什麼」讓讀者更懂",
                "方向很穩了，下一步把原因再扣回故事裡更細的一句就好",
            )
        if lv == "mid":
            return (
                "還差一個感受和原因：你當下覺得什麼，為什麼會這樣覺得",
                "你有在回應故事了，再補一句「我覺得……，因為……」會更清楚",
                "感受有方向了，現在只差把原因連回故事裡那一幕",
            )
        return (
            "還差一個感受和原因：你當下覺得什麼，為什麼會這樣覺得",
            "先把一個感受寫出來，再補一句因為故事裡哪一幕",
            "你可以先說我覺得……，再補因為……",
        )
    if s == "I":
        if lv == "high":
            return (
                "想法和理由都出來了，下一步把道理說得更貼故事：多一句「因為書裡……」",
                "方向清楚了，下一步試著用一句話說「這對我有什麼用」",
                "已經有學到了，下一步把『所以以後我會留意什麼』輕輕帶一句就好",
            )
        if lv == "mid":
            return (
                "還差一個想法和理由：你明白了什麼，故事裡哪一段可以說明",
                "你的想法快比較完整了，再補一句「因為故事裡……」就會更清楚",
                "這段重點是你學到什麼，還差一個故事裡的理由來說明",
            )
        return (
            "還差一個想法和理由：你明白了什麼，故事裡哪一段可以說明",
            "先把一個想法寫出來，再補一句故事裡的例子",
            "你可以先寫這件事讓我明白……，再補因為……",
        )
    if s == "D":
        if lv == "high":
            return (
                "行動已經很具體了，下一步試著加一句「什麼情況下我會提醒自己」",
                "方向很清楚了，下一步把第一步寫得更小、更像真的做得到",
                "已經有步驟了，下一步補一句「如果做不到，我先怎麼辦」讓計畫更穩",
            )
        if lv == "mid":
            return (
                "還差一個做得到的第一步：下次在什麼情況，你會先做什麼",
                "行動方向有了，請再寫出「下次遇到……我會先……」",
                "這段要寫成真的做得到，還差一個你可以先做的第一步",
            )
        return (
            "還差一個做得到的第一步：下次在什麼情況，你會先做什麼",
            "先寫出下次我會……，再補一句什麼時候做",
            "你可以先寫遇到……我就先……",
        )
    return ("還差一個明確主點，先補一句就好",)


def _suggestion_options(stage: str, strength: str) -> tuple[str, ...]:
    s = (stage or "O").strip().upper()
    lv = (strength or "mid").strip().lower()
    if s == "O":
        if lv == "high":
            return (
                "先挑書裡一件你稿子上還沒寫到的事，用三句話寫「誰、做了什麼、後來怎麼了」；再挑第二件也各用一小句補上，兩件之間用分號連起來。",
                "你可以先寫一句「接下來故事裡還有……」（要寫出具體事，不要只寫空話）；再寫一句接到你已經寫好的段落；最後檢查時間詞有沒有讓讀者跟上。",
                "如果書裡重點情節都已出現，就做小升級：先加一句細節形容；再補一句旁人反應；最後檢查人稱一致。",
            )
        if lv == "mid":
            return (
                "你可以先寫：一開始……，後來……",
                "試著接下去：先發生的是……，接著……",
                "先用一句整理順序：先……，再……",
            )
        return (
            "你可以先寫：故事裡先出現誰，他先做什麼",
            "試著接下去：先……，後來……",
            "先用一句寫出誰做了什麼，再補一句後來怎麼了",
        )
    if s == "R":
        if lv == "high":
            return (
                "你可以多寫一句：那一幕讓我最……，因為我看到……",
                "試著把感受變成畫面：像拍照一樣寫出你記得的一個鏡頭",
                "接著補一句：如果朋友讀不懂，我會怎麼再解釋我的感受",
            )
        return (
            "你可以先寫：我覺得……，因為……",
            "試著接下去：我那時候覺得……，因為看到……",
            "先寫感受再寫原因：我覺得……，是因為……",
        )
    if s == "I":
        if lv == "high":
            return (
                "你可以多寫一句：所以我以後在學校／家裡會留意……",
                "試著把道理說成小例子：像我有一次……",
                "接著補一句：如果朋友不同意，我會怎麼說明我的想法",
            )
        return (
            "你可以先寫：這件事讓我明白……，因為……",
            "試著接下去：我學到……，因為故事裡……",
            "先說你的想法，再補理由：這提醒我……，因為……",
        )
    if s == "D":
        if lv == "high":
            return (
                "你可以把第一步寫得更小：例如「明天下課我先……」",
                "試著加一句：我怎麼知道自己有做到",
                "接著補一句：如果忘記了，我會用什麼方法提醒自己",
            )
        return (
            "你可以先寫：下次遇到……，我會先……",
            "先寫第一步就好：下次我會先……，再……",
            "把行動寫小一點：當……的時候，我先……",
        )
    return ("試著先寫一句，再補一個小理由",)


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
        if any(k in t for k in ("一開始", "接著", "然後", "後來", "最後", "隔天", "第二天", "接下來")) and len(
            compact
        ) >= 18:
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


# O1 pass bar: need beginning conflict + mid/late development (not a thin 2-beat summary)
_O_PASS_CHARACTER_MARKERS: tuple[str, ...] = (
    "阿松爺爺",
    "阿松",
    "哎唷奶奶",
    "哎唷",
)
# Arc A: opening selfishness / not sharing
_O_PASS_ARC_EARLY: tuple[str, ...] = (
    "獨占",
    "自己吃",
    "不想分",
    "不分享",
    "不願意分享",
    "不太願意分享",
    "不肯分享",
    "不讓別人拿",
    "大口吃",
    "流口水",
    "炫耀",
)
# Arc B: middle hiding / stems / leaves / branches
_O_PASS_ARC_MID: tuple[str, ...] = (
    "柿子蒂",
    "陀螺",
    "藏",
    "倉庫",
    "葉子",
    "樹枝",
    "採下",
)
# Arc C: climax / turning point
_O_PASS_ARC_LATE: tuple[str, ...] = (
    "砍",
    "樹樁",
    "樹椿",
    "種子",
    "撒種",
    "後悔",
    "哭",
)


def o_draft_meets_pass_bar(student_text: str) -> bool:
    """True when O draft is ready to auto-pass (strong coverage).

    Requires character + markers from **all three** story arcs
    (early conflict → mid hiding/stems → late climax/turn), enough length,
    and at least 4 marker hits. Exact book wording is not required.

    Thin early+mid summaries must NOT auto-pass; AI/prompt still guide
    the student to add the missing arc.
    """
    t = (student_text or "").strip()
    if len(t) < 60:
        return False
    if not any(m in t for m in _O_PASS_CHARACTER_MARKERS):
        return False

    early, mid, late = o_draft_arc_flags(t)
    arcs_hit = sum(1 for x in (early, mid, late) if x)
    total_hits = 0
    for arc in (_O_PASS_ARC_EARLY, _O_PASS_ARC_MID, _O_PASS_ARC_LATE):
        total_hits += sum(1 for m in arc if m in t)
    return arcs_hit >= 3 and total_hits >= 4


def o_draft_arc_flags(student_text: str) -> tuple[bool, bool, bool]:
    """Return (has_early, has_mid, has_late) marker hits for O coverage coaching."""
    t = (student_text or "").strip()
    return (
        any(m in t for m in _O_PASS_ARC_EARLY),
        any(m in t for m in _O_PASS_ARC_MID),
        any(m in t for m in _O_PASS_ARC_LATE),
    )


_R_FEELING_MARKERS: tuple[str, ...] = (
    "生氣",
    "難過",
    "開心",
    "害怕",
    "擔心",
    "感動",
    "失望",
    "驚訝",
    "心疼",
    "不舒服",
    "嫉妒",
    "安心",
    "後悔",
    "不爽",
    "委屈",
    "溫暖",
    "覺得",
    "心情很糟",
    "很糟",
    "討厭",
    "不喜歡",
    "心裡怪怪",
)
_R_REASON_MARKERS: tuple[str, ...] = ("因為", "讓我", "看得", "想到這")
_R_SCENE_MARKERS: tuple[str, ...] = (
    "看到",
    "那一幕",
    "那時候",
    "一開始",
    "後來",
    "最後",
    "故意",
    "面前",
    "大口",
    "藏",
    "倉庫",
    "柿子蒂",
    "砍",
    "樹樁",
    "獨占",
)


def r_draft_meets_pass_bar(student_text: str) -> bool:
    """R pass: feeling + reason + concrete story beat; one thin sentence must not pass."""
    t = (student_text or "").strip()
    compact = re.sub(r"\s+", "", t)
    if len(compact) < 42:
        return False
    if not any(m in t for m in _R_FEELING_MARKERS):
        return False
    if not any(m in t for m in _R_REASON_MARKERS):
        return False
    # Need a concrete scene cue (not only 「不分享」)
    rich_story = any(m in t for m in _R_SCENE_MARKERS) or any(
        m in t for m in _O_PASS_ARC_MID + _O_PASS_ARC_LATE
    )
    if not rich_story:
        return False
    if not any(m in t for m in _O_PASS_CHARACTER_MARKERS + ("爺爺", "奶奶", "柿子")):
        return False
    return True


_I_LESSON_MARKERS: tuple[str, ...] = (
    "學到",
    "明白",
    "提醒",
    "道理",
    "啟發",
    "讓我知道",
    "我懂",
    "原來",
)
_I_GENERIC_ONLY: tuple[str, ...] = ("大方", "小氣", "善良", "分享很好", "要分享", "不要自私")


def i_draft_meets_pass_bar(student_text: str) -> bool:
    """I pass: lesson + story-supported why; ban one-line moral slogans."""
    t = (student_text or "").strip()
    compact = re.sub(r"\s+", "", t)
    if len(compact) < 42:
        return False
    if not any(m in t for m in _I_LESSON_MARKERS):
        return False
    has_story = any(m in t for m in _O_PASS_CHARACTER_MARKERS + ("爺爺", "奶奶", "柿子")) and (
        any(m in t for m in _O_PASS_ARC_EARLY + _O_PASS_ARC_MID + _O_PASS_ARC_LATE)
        or any(m in t for m in ("因為", "所以", "從", "看到", "後來", "最後"))
    )
    if not has_story:
        return False
    # Pure 「要大方／不要小氣」 without richer story beat → not enough
    only_generic = any(g in t for g in _I_GENERIC_ONLY) and not any(
        m in t for m in _O_PASS_ARC_MID + _O_PASS_ARC_LATE + ("大口", "獨占", "藏", "後悔", "種子")
    )
    if only_generic and len(compact) < 65:
        return False
    return True


_D_ACTION_MARKERS: tuple[str, ...] = ("我會", "我要", "下次", "打算", "先", "再")
_D_SITUATION_MARKERS: tuple[str, ...] = ("如果", "遇到", "當", "時候", "對", "跟", "和")
_D_CONCRETE_MARKERS: tuple[str, ...] = (
    "同學",
    "家人",
    "朋友",
    "先問",
    "一起",
    "輪流",
    "排隊",
    "零食",
    "玩具",
    "東西",
    "分給",
    "借給",
    "說對不起",
    "深呼吸",
    "等一下",
    "一步",
    "再",
)
_D_GENERIC_ACTION: tuple[str, ...] = ("幫忙", "幫助", "變好", "改進", "努力", "更好", "加油")


def d_draft_meets_pass_bar(student_text: str) -> bool:
    """D pass: concrete when/who/how; ban bare 「我會去幫忙」."""
    t = (student_text or "").strip()
    compact = re.sub(r"\s+", "", t)
    if len(compact) < 40:
        return False
    if not any(m in t for m in _D_ACTION_MARKERS):
        return False
    if not any(m in t for m in _D_SITUATION_MARKERS):
        return False
    has_concrete = any(m in t for m in _D_CONCRETE_MARKERS) or (
        "先" in t and "再" in t
    )
    if not has_concrete:
        # Generic-only help slogans
        if any(g in t for g in _D_GENERIC_ACTION) and len(compact) < 65:
            return False
        return False
    # Still block ultra-generic even with 如果/遇到
    if (
        any(g in t for g in ("幫忙", "幫助"))
        and not any(m in t for m in _D_CONCRETE_MARKERS if m not in ("再",))
        and "先" not in t
        and len(compact) < 60
    ):
        return False
    return True


def stage_draft_meets_pass_bar(stage: str, student_text: str) -> bool:
    s = (stage or "O").strip().upper()
    if s == "O":
        return o_draft_meets_pass_bar(student_text)
    if s == "R":
        return r_draft_meets_pass_bar(student_text)
    if s == "I":
        return i_draft_meets_pass_bar(student_text)
    if s == "D":
        return d_draft_meets_pass_bar(student_text)
    return False


def thin_stage_coaching(stage: str, student_text: str) -> tuple[str, str]:
    """One missing + suggestion when draft is below the stage pass bar."""
    s = (stage or "O").strip().upper()
    t = (student_text or "").strip()
    compact = re.sub(r"\s+", "", t)

    if s == "O":
        has_early, has_mid, has_late = o_draft_arc_flags(t)
        if has_early and has_mid and not has_late:
            return (
                "你已經寫到故事開頭和中間，最後的改變還沒有說清楚。",
                "想一想：故事最後發生了什麼？",
            )
        if has_early and has_late and not has_mid:
            return (
                "你已經寫到故事開頭和最後，中間發生什麼還不清楚。",
                "想一想：故事中間又發生了什麼？",
            )
        if has_mid and has_late and not has_early:
            return (
                "你已經寫到故事中間和最後，開頭發生什麼還不清楚。",
                "想一想：故事一開始是誰做了什麼？",
            )
        if len(t) < 60:
            if has_early:
                return (
                    "你已經寫出故事開頭，中間發生什麼還不清楚。",
                    "想一想：接著發生了哪一件事？",
                )
            if has_mid:
                return (
                    "你寫到故事中間的事了，但開頭還不清楚。",
                    "想一想：故事一開始是誰做了什麼？",
                )
            if has_late:
                return (
                    "你寫到故事最後的事了，但開頭還不清楚。",
                    "想一想：故事一開始是誰做了什麼？",
                )
            return (
                "目前還看不出故事先發生什麼。",
                "想一想：故事一開始是誰做了什麼？",
            )
        return (
            "人物和事情都有了，再把其中一件事說清楚一點。",
            "回到 O 觀察格，補一句：故事裡，＿＿做了＿＿。",
        )

    if s == "R":
        has_feeling = any(m in t for m in _R_FEELING_MARKERS)
        has_reason = any(m in t for m in _R_REASON_MARKERS)
        has_scene = any(m in t for m in _R_SCENE_MARKERS) or any(
            m in t for m in _O_PASS_ARC_MID + _O_PASS_ARC_LATE
        )
        if has_feeling and has_reason and not has_scene:
            return (
                "你有感受和「因為」了，再補「書裡哪一幕」會更清楚，例如大口吃、藏倉庫或砍樹。",
                "哪一幕讓你最有這種感覺？看到誰做了什麼？",
            )
        if has_feeling and not has_reason:
            return (
                "你有寫出感受了，請再補「因為書裡哪一件事」。",
                "試著寫：我覺得……，因為故事裡……。",
            )
        if len(compact) < 42:
            return (
                "目前還偏短，請把感受、原因，以及書裡那一幕都寫清楚一點。",
                "可以寫：我覺得……，因為我看到……。",
            )
        return (
            "請把感受、原因和書裡具體那一幕都寫出來，R 才算達標。",
            "哪一幕讓你有這個感覺？再多寫一句畫面。",
        )

    if s == "I":
        has_lesson = any(m in t for m in _I_LESSON_MARKERS)
        if has_lesson and not any(m in t for m in _O_PASS_ARC_MID + _O_PASS_ARC_LATE + ("大口", "獨占", "藏", "後悔")):
            return (
                "你有寫到學到什麼了，再補「故事裡哪一段讓你這樣想」，不要只說要大方／不要小氣。",
                "故事裡哪一件事讓你明白這個道理？",
            )
        if len(compact) < 42:
            return (
                "目前還偏短，請寫出學到的道理，並連回書裡一件具體的事。",
                "可以寫：我學到……，因為故事裡……。",
            )
        return (
            "請把「學到什麼」和「故事哪一段支持你」都寫清楚，I 才算達標。",
            "從阿松爺爺哪一件事，你看出這個道理？",
        )

    # D
    if any(g in t for g in ("幫忙", "幫助")) and not any(
        m in t for m in _D_CONCRETE_MARKERS if m not in ("再",)
    ):
        return (
            "「去幫忙」方向對了，再寫清楚：什麼時候、幫誰、先做哪一步。",
            "可以寫：下次在……的時候，我會先……，再……。",
        )
    if len(compact) < 40:
        return (
            "目前還偏短，請寫出一個生活裡真的做得到的小行動，並說何時／對誰。",
            "可以寫：如果遇到……，我會先……。",
        )
    return (
        "請把行動寫得更具體：什麼情況、對誰、先做哪一步，D 才算達標。",
        "在什麼情況下你會這樣做？第一步是什麼？",
    )

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
            "O": "先把事情寫出來就很棒了",
            "R": "先把感受說出來就有進步了",
            "I": "先把你的想法說出來就是很重要的一步",
            "D": "先寫出第一步行動就會清楚很多",
        },
        "mid": {
            "O": "方向對了，下一步把順序再講清楚",
            "R": "你有感受方向了，再補原因就更清楚",
            "I": "你有想法了，再補故事理由會更清楚",
            "D": "你有行動方向了，再補情況就更像真的會做",
        },
        "high": {
            "O": "你已經抓到重點事件了，現在只要再清楚一點",
            "R": "你的感受和原因都有了，再順一下就很好",
            "I": "你的想法和理由都有了，再補一句會更完整",
            "D": "你的行動很具體了，再把第一步寫得更順一點",
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

    if "對齊教材" in m0:
        if not s0:
            s0 = "請依書裡真實的人與事件重寫"
        return [m0], [s0]

    strength = _draft_strength(stage, student_text)
    seed = f"{stage}|{strength}|{student_text}|{m0}|{s0}"

    if (not m0) or any(tok in m0 for tok in _VAGUE_FEEDBACK_TOKENS):
        miss_opts = _missing_options(stage, strength)
        # O+high 的第三句是「書裡重點都已寫到才做小修」；fallback 抽選時沒有真的比對全文，勿用該句當預設。
        if (stage or "").strip().upper() == "O" and strength == "high" and len(miss_opts) >= 3:
            miss_opts = miss_opts[:2]
        base = _pick_phrase(miss_opts, seed)
        m0 = f"{_strength_prefix(stage, strength)}：{base}"

    if (not s0) or any(tok in s0 for tok in _VAGUE_FEEDBACK_TOKENS):
        sug_opts = _suggestion_options(stage, strength)
        if (stage or "").strip().upper() == "O" and strength == "high" and len(sug_opts) >= 3:
            sug_opts = sug_opts[:2]
        s0 = _pick_phrase(sug_opts, f"sug|{seed}")

    if (stage or "").strip().upper() == "O" and student_o_meta_stuck((student_text or "").strip()):
        if missing_looks_book_grounding_priority(m0):
            return [_child_friendly_text(m0)], [_child_friendly_text(s0)]
        bookish = any(
            k in m0
            for k in (
                "阿松",
                "爺爺",
                "柿子",
                "倉庫",
                "書裡",
                "教材",
                "故事裡",
                "主人公",
                "哎唷",
            )
        )
        canned = ("讀的人還看不出" in m0) or ("看不出故事" in m0)
        if canned and not bookish:
            m0 = GENAI_META_MISSING_FALLBACK
            if "摘要" not in s0 and "摘錄" not in s0:
                s0 = "先翻到故事摘要，挑一句「誰做了什麼」，照那句的精神寫成你的第一段。"

    return [_child_friendly_text(m0)], [_child_friendly_text(s0)]

_O_GENERIC_PHRASES = (
    "中間衝突",
    "轉變",
    "挑一件",
    "選一個",
    "先挑書裡",
    "三句話",
    "誰—做了什麼",
    "誰、做了什麼",
    "再去想",
    "還沒提到的一段",
)


_GROUNDING_MISSING_CUES = (
    "不在書裡",
    "書裡沒有",
    "故事裡沒有",
    "故事裡其實沒有",
    "其實沒有",
    "不是書裡",
    "好像不是書裡",
    "不像書裡",
    "沒有這件事",
    "書裡說的是",
    "書裡叫做",
    "看起來不在書裡",
    "對齊教材",
    "書裡出現的是",
    "書裡比較像是",
    "不是「",
    "這個詞好像不在",
    "書裡真的",
    "對回書裡",
    "改成書裡",
    "書裡實際",
)


def missing_looks_book_grounding_priority(missing: list[str] | str) -> bool:
    if isinstance(missing, list):
        m = (missing[0] if missing else "").strip()
    else:
        m = (missing or "").strip()
    return any(k in m for k in _GROUNDING_MISSING_CUES)


def _book_character_names_in_draft(student_text: str, book_pack: dict | None) -> list[str]:
    """Return character labels from the draft that match the book (prefer what student wrote)."""
    t = (student_text or "").strip()
    if not t or not isinstance(book_pack, dict):
        return []
    found: list[str] = []
    for item in book_pack.get("characters") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        if name in t:
            found.append(name)
            continue
        # Alias: student wrote 奶奶 / 爺爺 but book lists full name
        if name.endswith("爺爺") and "爺爺" in t:
            label = "爺爺"
            if label not in found and not any("爺爺" in n for n in found):
                found.append(label)
        elif name.endswith("奶奶") and "奶奶" in t:
            label = "奶奶"
            if label not in found and not any("奶奶" in n for n in found):
                found.append(label)
    out: list[str] = []
    for n in found:
        if n not in out:
            out.append(n)
    return out[:2]


def build_grounding_safe_praise(
    *,
    stage: str,
    student_text: str = "",
    book_pack: dict | None = None,
) -> str:
    """Praise only book-aligned effort / names — never celebrate fabricated plot as 'done'."""
    s = (stage or "O").strip().upper()
    names = _book_character_names_in_draft(student_text, book_pack)
    name_bit = ""
    if names:
        quoted = "、".join(f"「{n}」" for n in names)
        name_bit = f"你有寫到{quoted}，人物方向有抓到；"

    if s == "O":
        if name_bit:
            return f"{name_bit}事件要再對回書裡真的發生的事。"
        return "你有試著寫出人物和事件，這是 O 段需要的方向；只是情節要再對回書裡。"
    if s == "R":
        if name_bit:
            return f"{name_bit}感受可以留，但原因要接回書裡真的發生的事。"
        return "你有試著寫出自己的感受，這很好；只是原因要再連回書裡真的發生的事。"
    if s == "I":
        if name_bit:
            return f"{name_bit}想法可以留，但道理要接回書裡真的發生的事。"
        return "你有試著寫出想法，這很好；只是道理要再接回書裡真的發生的事。"
    if s == "D":
        return "你有試著寫出下一步，這很好；只是行動要再接回這本書提醒你的地方。"
    return "你有試著寫，我已經看到了；只是內容要再對回書裡。"


def scrub_praise_for_grounding_issue(
    *,
    stage: str,
    praise: str | None,
    missing: list[str] | str,
    student_text: str = "",
    book_pack: dict | None = None,
) -> str:
    """
    When missing is about book mismatch, do not keep praise that quotes / affirms the wrong event.
    """
    if not missing_looks_book_grounding_priority(missing):
        return (praise or "").strip()
    return build_grounding_safe_praise(
        stage=stage,
        student_text=student_text,
        book_pack=book_pack,
    )


def scrub_anchor_quote_for_grounding(
    *,
    quote: object,
    missing: list[str] | str,
    student_text: str = "",
    book_pack: dict | None = None,
) -> str | None:
    """If anchor quote embeds fabricated plot, fall back to a book character name only."""
    if not missing_looks_book_grounding_priority(missing):
        q = str(quote or "").strip()
        return q or None
    names = _book_character_names_in_draft(student_text, book_pack)
    if names:
        return names[0]
    # Keep short name-like quote only if it does not look like an event clause
    q = str(quote or "").strip()
    if q and len(q) <= 6 and "送" not in q and "花" not in q:
        return q
    return None


_APPEND_AFTER_WRONG_CUES = (
    "後面加",
    "後面加上",
    "後面補",
    "之後加",
    "之後加上",
    "之後補",
    "後面再加",
    "後面再補",
)


def rewrite_grounding_append_suggestions(
    *,
    stage: str,
    missing: list[str],
    suggestions: list[str],
    example: str | None = None,
) -> tuple[list[str], list[str], str | None]:
    """When missing flags fabricated content, ban 'append after wrong sentence' coaching."""
    if not missing_looks_book_grounding_priority(missing):
        return missing, suggestions, example

    s0 = (suggestions[0] if suggestions else "").strip()
    looks_append = bool(s0) and (
        any(c in s0 for c in _APPEND_AFTER_WRONG_CUES)
        or bool(re.search(r"在[『「].{1,40}[』」].{0,12}(後面|之後)", s0))
    )
    if looks_append or not s0:
        stage_u = (stage or "O").strip().upper()
        replace_map = {
            "O": "請先把那一句改掉，改寫成書裡真的發生的事：誰做了什麼？",
            "R": "請先把不符合書裡的那一句改掉，再寫你的感受和原因。",
            "I": "請先把不符合書裡的那一句改掉，再寫你從故事學到的道理。",
            "D": "請先對回這本書想提醒你的事，再寫你下次要怎麼做。",
        }
        suggestions = [replace_map.get(stage_u, replace_map["O"])]

    # Example must not scaffold onto the fabricated clause
    ex = (example or "").strip() if example is not None else ""
    if ex and (
        any(c in ex for c in _APPEND_AFTER_WRONG_CUES)
        or bool(re.search(r"在[『「].{1,40}[』」].{0,12}(後面|之後)", ex))
    ):
        example = None

    return missing, suggestions, example


def _o_missing_looks_grounding_priority(missing: list[str]) -> bool:
    return missing_looks_book_grounding_priority(missing)


def _o_feedback_looks_generic_coaching(missing: list[str], suggestions: list[str]) -> bool:
    blob = (missing[0] if missing else "") + (suggestions[0] if suggestions else "")
    return any(p in blob for p in _O_GENERIC_PHRASES)


def _compact_zh(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _clauses_from_event_line(ev: str) -> list[str]:
    parts = re.split(r"[，。、；：／\n]+", ev)
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def _story_event_kw_score(clause: str) -> int:
    for i, kw in enumerate(("倉庫", "柿子葉", "葉子", "樹枝", "砍", "樹樁", "樹椿", "種子", "獨占", "炫耀", "羨慕")):
        if kw in clause:
            return 50 - i
    return 0


def apply_o_key_event_gaps(
    *,
    stage: str,
    strength: str,
    student_text: str,
    key_events: Any,
    missing: list[str],
    suggestions: list[str],
) -> tuple[list[str], list[str]]:
    """
    When O draft already has several beats (high), replace generic「挑一段／中間衝突」
    with concrete clauses from key_events that do not appear in the student text.
    Does not override book-grounding corrections.
    """
    if (stage or "").strip().upper() != "O" or (strength or "").strip().lower() != "high":
        return missing, suggestions
    if _o_missing_looks_grounding_priority(missing):
        return missing, suggestions
    # Already at O1 達標 bar → do not keep demanding more key-event coverage
    if o_draft_meets_pass_bar(student_text):
        return missing, suggestions
    if not isinstance(key_events, list) or not key_events:
        return missing, suggestions

    if len(_compact_zh(student_text)) < 18:
        return missing, suggestions

    # Keep concrete book events internal. Student-facing feedback only names
    # the missing story position, which also avoids semantic repeat requests.
    miss, sug = thin_stage_coaching("O", student_text)
    return [_child_friendly_text(miss)], [_child_friendly_text(sug)]


_QUOTE_SPAN_RE = re.compile(r"「([^」]{2,48})」")
_COMMON_SCENE_CUES: tuple[str, ...] = (
    "故意在大家面前大口吃",
    "在大家面前大口吃",
    "大口吃甜柿子",
    "大口吃",
    "藏進倉庫",
    "藏到倉庫",
    "柿子蒂",
    "砍了樹",
    "只剩樹樁",
    "樹樁",
    "撒種子",
)


def _compact_zh(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _revision_text_covered_by_draft(message: str, draft_compact: str) -> bool:
    """True when a revision prompt is asking for content already present in the draft."""
    msg = message or ""
    if not msg or not draft_compact:
        return False
    for span in _QUOTE_SPAN_RE.findall(msg):
        compact_span = _compact_zh(span)
        if len(compact_span) >= 4 and compact_span in draft_compact:
            return True
    for cue in _COMMON_SCENE_CUES:
        if cue in msg and cue in draft_compact:
            return True
    return False


def scrub_revision_prompts_already_in_draft(
    stage: str,
    student_text: str,
    missing: list[str],
    suggestions: list[str],
    example: str | None = None,
) -> tuple[list[str], list[str], str | None]:
    """Rewrite missing/suggestions that re-ask for phrases already in the student draft.

    Used when the draft is still below the stage pass bar (so we keep guiding),
    but the model keeps pointing at a scene/feeling the student already wrote —
    the classic 「鬼打牆」 loop. Grounding / book-mismatch missings are left alone.
    """
    if missing_looks_book_grounding_priority(missing):
        return missing, suggestions, example

    draft_compact = _compact_zh(student_text)
    m0 = (missing[0] if missing else "").strip()
    s0 = (suggestions[0] if suggestions else "").strip()
    if not (
        _revision_text_covered_by_draft(m0, draft_compact)
        or _revision_text_covered_by_draft(s0, draft_compact)
    ):
        return missing, suggestions, example

    stage_u = (stage or "O").strip().upper()
    new_m, new_s = thin_stage_coaching(stage_u, student_text)
    if (
        _revision_text_covered_by_draft(new_m, draft_compact)
        or _revision_text_covered_by_draft(new_s, draft_compact)
        or stage_draft_meets_pass_bar(stage_u, student_text)
    ):
        # Pass-bar-ready drafts should usually be promoted by the route layer;
        # if we still land here, nudge a *different* deepening angle without
        # repeating the same quoted scene.
        if stage_u == "R":
            new_m = "你已經有感受、原因和書裡畫面了；若還想加強，用自己的話把「為什麼特別有這種感覺」再說半句就好，不必重寫同一句。"
            new_s = "哪一個細節最讓你在意？用自己的話說一點就好。"
        elif stage_u == "I":
            new_m = "你已經有寫到學到什麼了；若還想加強，用自己的話說明「為什麼這段故事讓你這樣想」，不要重複同一句情節。"
            new_s = "是哪一個轉折讓你最有感？再補半句理由就好。"
        elif stage_u == "D":
            new_m = "你已經有寫到具體行動了；若還想加強，再補「什麼時候／對誰」其中一點即可，不必重寫同一句。"
            new_s = "這個行動會先發生在什麼場合？或先對誰做？"
        else:
            new_m = "請把還沒寫清楚的大事件再補一點，不要重複已經寫過的同一句。"
            new_s = "哪一段（開頭／中間／結尾）還可以再具體一點？"

    new_ex = example
    if example and _revision_text_covered_by_draft(example, draft_compact):
        new_ex = None
    return [_child_friendly_text(new_m)], [_child_friendly_text(new_s)], new_ex
