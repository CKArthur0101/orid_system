from __future__ import annotations

import re


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
