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
)


def missing_looks_book_grounding_priority(missing: list[str] | str) -> bool:
    if isinstance(missing, list):
        m = (missing[0] if missing else "").strip()
    else:
        m = (missing or "").strip()
    return any(k in m for k in _GROUNDING_MISSING_CUES)


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
    if not isinstance(key_events, list) or not key_events:
        return missing, suggestions

    compact_s = _compact_zh(student_text)
    if len(compact_s) < 18:
        return missing, suggestions

    hints: list[str] = []
    for raw in key_events:
        ev = str(raw).strip()
        if len(ev) < 10:
            continue
        ev_c = ev.replace(" ", "")
        if ev_c and ev_c in compact_s:
            continue
        clauses = _clauses_from_event_line(ev)
        if not clauses and len(ev) >= 10:
            clauses = [ev[: min(36, len(ev))]]
        miss_candidates = [c for c in clauses if c and c not in compact_s]
        if not miss_candidates:
            continue
        best = max(miss_candidates, key=lambda c: (_story_event_kw_score(c), len(c)))
        cand = best.strip()[:42]
        if cand and cand not in hints:
            hints.append(cand)
        if len(hints) >= 4:
            break

    if len(hints) < 2 and not _o_feedback_looks_generic_coaching(missing, suggestions):
        return missing, suggestions
    if not hints:
        return missing, suggestions

    hints.sort(key=_story_event_kw_score, reverse=True)
    hints = hints[:3]

    mprev = (missing[0] if missing else "").strip()
    if mprev:
        covered = 0
        for h in hints:
            frag = h[:12] if len(h) >= 12 else h
            if len(frag) >= 4 and frag in mprev:
                covered += 1
        if covered >= len(hints):
            return missing, suggestions

    joined = "；".join(f"「{h}」" for h in hints[:3])
    miss = f"書裡還有這些情節你幾乎還沒寫進稿子：{joined}。先挑最容易接的一句補在合適的位置就好。"
    if len(miss) > 200:
        miss = miss[:197] + "…"

    if len(hints) >= 2:
        sug = (
            f"先加一小句接在「藏柿子／柿子蒂」附近，寫到「{hints[0]}」；"
            f"再加一小句寫「{hints[1]}」；最後用「然後／隔天／最後」把順序讀一次，看讀者跟不跟得上。"
        )
    else:
        sug = f"先加一小句寫「{hints[0]}」，再用分號接到你已經寫好的段落，讀者就比較跟得上。"

    return [_child_friendly_text(miss)], [_child_friendly_text(sug)]

