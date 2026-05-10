from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import json
import re

from .shared import build_book_context_block

Stage = str  # "O" | "R" | "I" | "D"

_ATTACK_PATTERNS = [
    r"(你|妳|他|她|你們|妳們)\s*(是|很|超|真|也太)?\s*[^ \n]{0,4}(笨|蠢|爛|噁|討厭|白痴|白癡|智障|低能|廢物)",
    r"(你|妳|他|她)\s*(去|給我去)\s*(死|滾)",
]
_PROFANITY_MIN = [
    "幹", "靠北", "操", "媽的", "他媽", "白痴", "白癡", "智障", "廢物", "去死",
]

_JSON_RE = re.compile(r"\{[\s\S]*\}")
_GENERIC_Q_PATTERNS = [
    r"故事發生了什麼",
    r"說說故事",
    r"有什麼感覺",
    r"提醒我們什麼",
    r"你會怎麼做",
]
_DAILY_LIFE_KEYWORDS = [
    "今天", "昨天", "明天", "早餐", "午餐", "晚餐", "便當", "飲料", "咖啡", "手機", "遊戲",
    "睡覺", "起床", "上課", "下課", "回家", "逛街", "天氣", "考試", "排骨", "雞排", "奶茶",
    "ktv", "唱歌", "夜店", "酒吧", "球賽", "nba", "wnba", "演唱會", "打電動",
]
_STORY_CUE_KEYWORDS = [
    "故事", "書裡", "一開始", "後來", "接著", "最後", "改變", "分享", "柿子", "種子",
    "爺爺", "奶奶", "孩子", "小朋友", "大家一起", "不想分", "提醒", "誤會",
]
_COMMON_STORY_ANCHORS = {
    "故事", "書裡", "阿松", "爺爺", "奶奶", "小朋友", "孩子", "柿子", "樹", "分享", "最後",
}
_ABSURD_MISMATCH_KEYWORDS = [
    "火箭", "外星人", "魔法", "飛船", "超能力", "機器人", "總統", "炸彈", "核彈", "穿越",
]
_UNSUPPORTED_EVENT_KEYWORDS = [
    "過世",
    "去世",
    "死亡",
    "死掉",
    "死了",
    "生病",
    "住院",
    "車禍",
    "結婚",
    "離婚",
    "搬家",
    "旅行",
]
_ACTION_EVENT_KEYWORDS = [
    "打",
    "揍",
    "毆",
    "踢",
    "砍",
    "殺",
    "欺負",
    "霸凌",
]


def _looks_unsafe_by_structure(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    t_nospace = re.sub(r"\s+", "", t)
    for p in _ATTACK_PATTERNS:
        if re.search(p, t_nospace):
            return True
    for w in _PROFANITY_MIN:
        if w in t_nospace:
            return True
    return False


def _one_question(text: str) -> str:
    t = (text or "").strip().replace("?", "？")
    if not t:
        return "你可以再說清楚一點嗎？"
    if "？" not in t:
        return t + "？"
    first = t.split("？", 1)[0].strip()
    return first + "？"


def _extract_anchor(student_text: str) -> str:
    t = re.sub(r"[「」『』\"'，。！？：；、（）()\[\]{}\s]+", " ", (student_text or "").strip())
    parts = [p.strip() for p in t.split(" ") if p.strip()]
    # Only use CJK anchors to avoid echoing gibberish/latin noise.
    for p in parts:
        if re.search(r"[一-龥]", p) and 2 <= len(p) <= 8:
            return p
    t2 = re.sub(r"\s+", "", t)
    m = re.search(r"[一-龥]{2,8}", t2)
    return m.group(0) if m else ""


def _anchor_is_daily_life(anchor: str) -> bool:
    a = (anchor or "").strip()
    if not a:
        return False
    return any(k in a for k in _DAILY_LIFE_KEYWORDS )


def _normalize_match_text(text: str) -> str:
    t = re.sub(r"[\s「」『』\"'，。！？：；、（）()\[\]{}、]+", "", (text or "").strip())
    return t.replace("\u4f54", "\u5360")


def _extract_book_terms(book_pack: Optional[dict[str, Any]]) -> set[str]:
    terms: set[str] = set()
    if not isinstance(book_pack, dict):
        return terms

    def add_term(value: Any) -> None:
        s = str(value or "").strip()
        if not s:
            return
        s_clean = _normalize_match_text(s)
        if 2 <= len(s_clean) <= 10:
            terms.add(s_clean)
        for token in re.findall(r"[一-龥A-Za-z]{2,8}", s):
            token = _normalize_match_text(token)
            if 2 <= len(token) <= 8:
                terms.add(token)

    add_term(book_pack.get("book_title") or "")
    for item in (book_pack.get("core_theme") or [])[:6]:
        add_term(item)
    for item in (book_pack.get("setting") or [])[:6]:
        add_term(item)
    for item in (book_pack.get("key_events") or [])[:8]:
        add_term(item)
    for item in (book_pack.get("characters") or [])[:8]:
        if isinstance(item, dict):
            add_term(item.get("name") or "")
            add_term(item.get("role") or "")
        else:
            add_term(item)

    terms.update(_STORY_CUE_KEYWORDS)
    return {x for x in terms if x}


def looks_story_related_to_book(student_text: str, book_pack: Optional[dict[str, Any]]) -> bool:
    text_norm = _normalize_match_text(student_text)
    if not text_norm:
        return False

    book_terms = _extract_book_terms(book_pack)
    if any(term and term in text_norm for term in book_terms):
        return True

    if any(k in text_norm for k in _STORY_CUE_KEYWORDS):
        return True

    opinion_like_patterns = [
        r"(他|她|他們|大家).{0,4}(很|太|不|有)",
        r"這樣.{0,4}(很|不)",
        r"(改變|分享|提醒|誤會|一起)",
    ]
    return any(re.search(p, text_norm) for p in opinion_like_patterns)


def looks_obviously_offtopic(student_text: str, book_pack: Optional[dict[str, Any]]) -> bool:
    text_norm = _normalize_match_text(student_text)
    if not text_norm:
        return False
    if looks_story_related_to_book(student_text, book_pack):
        return False

    if text_norm.startswith("我今天") or text_norm.startswith("我昨天") or text_norm.startswith("我剛剛"):
        return True

    if any(k in text_norm for k in _DAILY_LIFE_KEYWORDS):
        return True

    # Standalone Latin/number tokens (e.g. "NBA", random gibberish) should be
    # treated as off-topic unless they match book terms.
    if re.fullmatch(r"[A-Za-z0-9_]{2,40}", text_norm):
        return True

    # Common mixed CJK+Latin daily topics that often bypass the strict patterns.
    if re.search(r"(唱歌|去唱|ktv|nba|wnba|夜店|酒吧)", text_norm, flags=re.IGNORECASE):
        return True

    # Mixed-symbol/no-CJK short nonsense often appears in student noise input.
    if (not re.search(r"[一-龥]", student_text or "")) and re.fullmatch(r"[A-Za-z0-9_\-\+\=\.\, ]{4,60}", student_text.strip()):
        return True

    daily_patterns = [
        r"我(要|想|去|在).{0,8}(吃|買|玩|睡|上課|下課|回家)",
        r"(午餐|早餐|晚餐|便當|手機|遊戲|天氣)",
    ]
    return any(re.search(p, text_norm) for p in daily_patterns)


def _extract_story_reference_blob(book_pack: Optional[dict[str, Any]]) -> str:
    if not isinstance(book_pack, dict):
        return ""
    parts: list[str] = []
    for x in (book_pack.get("key_events") or [])[:20]:
        s = str(x or "").strip()
        if s:
            parts.append(s)
    for x in (book_pack.get("story_excerpts") or [])[:20]:
        s = str(x or "").strip()
        if s:
            parts.append(s)
    for x in (book_pack.get("core_theme") or [])[:20]:
        s = str(x or "").strip()
        if s:
            parts.append(s)
    for x in (book_pack.get("setting") or [])[:12]:
        s = str(x or "").strip()
        if s:
            parts.append(s)
    t = (book_pack.get("book_title") or "")
    if str(t).strip():
        parts.append(str(t).strip())
    for item in (book_pack.get("characters") or [])[:12]:
        if isinstance(item, dict):
            for k in ("name", "role"):
                s = str(item.get(k) or "").strip()
                if s:
                    parts.append(s)
        else:
            s = str(item or "").strip()
            if s:
                parts.append(s)
    return _normalize_match_text(" ".join(parts))


def _strip_story_framing_for_grounding(text: str) -> str:
    """
    Remove common student framing words before grounding token checks.
    Otherwise "故事裡先發生了爺爺..." gets greedily tokenized into unsupported
    chunks like "故事裡先發".
    """
    t = _normalize_match_text(text)
    prefixes = (
        "故事裡先發生了",
        "故事裡先發生",
        "故事先發生了",
        "故事先發生",
        "書裡先發生了",
        "書裡先發生",
        "書中先發生了",
        "書中先發生",
        "先發生了",
        "先發生",
        "一開始",
        "後來",
        "接著",
        "最後",
        "然後",
    )
    changed = True
    while changed:
        changed = False
        for p in prefixes:
            if t.startswith(p):
                t = t[len(p) :]
                changed = True
    return t


def _has_unsupported_event_keyword(text_norm: str, reference_blob: str) -> bool:
    """
    Character overlap alone is not enough. If a student adds a concrete event
    keyword that is absent from the book context (e.g. "爺爺過世"), treat it as
    an unsupported story event rather than praising the content.
    """
    if not text_norm or not reference_blob:
        return False
    for kw in _UNSUPPORTED_EVENT_KEYWORDS:
        k = _normalize_match_text(kw)
        if k and k in text_norm and k not in reference_blob:
            return True
    return False


def _has_unsupported_action_event_claim(text_norm: str, reference_blob: str) -> bool:
    """
    Catch fabricated action claims like "爺爺打奶奶" that may share character words
    with the book but do not appear as an actual event relation in BOOK_CONTEXT.
    """
    if not text_norm or not reference_blob:
        return False
    spans = re.findall(r"[一-龥]{0,4}(?:打|揍|毆|踢|砍|殺|欺負|霸凌)[一-龥]{0,4}", text_norm)
    for sp in spans:
        s = _normalize_match_text(sp)
        if len(s) < 3:
            continue
        if s in reference_blob:
            continue
        # If both sides around the verb relation are unseen in reference, treat as unsupported.
        if any(k in s for k in _ACTION_EVENT_KEYWORDS):
            m = re.search(r"(打|揍|毆|踢|砍|殺|欺負|霸凌)", s)
            if not m:
                continue
            i = m.start()
            left = s[max(0, i - 2) : i + 1]   # e.g. 爺爺打
            right = s[i : min(len(s), i + 3)]  # e.g. 打奶奶
            if left and right and left not in reference_blob and right not in reference_blob:
                return True
    return False


def _cjk_token_grounded_in_reference(token: str, reference_blob: str) -> bool:
    """
    嚴格子字串 t in ref 容易因 2–5 字斷詞切壞人名/詞組而誤判。
    改為：整段命中，或以「二字組」在教材字串中的覆蓋率推斷是否扣得回教材。
    """
    t = (token or "").strip()
    if not t or not reference_blob:
        return False
    if t in reference_blob:
        return True
    if len(t) < 2:
        return t in reference_blob
    bigrams = [t[i : i + 2] for i in range(len(t) - 1)]
    hits = sum(1 for g in bigrams if g in reference_blob)
    if hits == 0:
        return False
    return (hits / len(bigrams)) >= 0.25


def _extract_cjk_tokens(text: str) -> list[str]:
    raw = re.findall(r"[一-龥]{2,5}", _normalize_match_text(text))
    # preserve order while removing duplicates
    seen: set[str] = set()
    out: list[str] = []
    for t in raw:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


_LATIN_HALLUC_ALLOWLIST = frozenset(
    {
        "orid",
        "nba",
        "wnba",
        "ktv",
        "www",
        "com",
        "pdf",
        "url",
        "app",
        "gpt",
    }
)


def looks_likely_latin_hallucination(
    student_text: str, book_pack: Optional[dict[str, Any]]
) -> bool:
    """
    Mixed Chinese + Latin proper nouns (e.g. celebrity names) often bypass CJK-only
    token overlap. Flag Latin runs that do not appear anywhere in the book reference.
    """
    s = (student_text or "").strip()
    if not s or not isinstance(book_pack, dict):
        return False
    if not re.search(r"[A-Za-z]{3,}", s):
        return False
    reference_blob = _extract_story_reference_blob(book_pack)
    if not reference_blob:
        return False
    blob_lower = reference_blob.lower()
    blob_compact = _normalize_match_text(reference_blob).lower()
    for m in re.finditer(r"[A-Za-z]{3,}", s):
        w = m.group(0).lower()
        if w in _LATIN_HALLUC_ALLOWLIST:
            continue
        if w in blob_lower or w in blob_compact:
            continue
        return True
    return False


def looks_likely_factual_mismatch(student_text: str, book_pack: Optional[dict[str, Any]]) -> bool:
    """
    Detect "story-related but factually off" messages.
    This is intentionally conservative: only returns True on clear mismatch signs.
    """
    text = (student_text or "").strip()
    if len(text) < 4:
        return False
    if not looks_story_related_to_book(text, book_pack):
        return False
    if looks_obviously_offtopic(text, book_pack):
        return False

    text_norm = _normalize_match_text(text)
    if any(k in text_norm for k in _ABSURD_MISMATCH_KEYWORDS):
        return True

    reference_blob = _extract_story_reference_blob(book_pack)
    if not reference_blob:
        return False
    if _has_unsupported_event_keyword(text_norm, reference_blob):
        return True
    if _has_unsupported_action_event_claim(text_norm, reference_blob):
        return True

    tokens = _extract_cjk_tokens(text)
    if not tokens:
        return False
    content_tokens = [t for t in tokens if t not in _COMMON_STORY_ANCHORS]
    if not content_tokens:
        return False

    matched = [t for t in content_tokens if _cjk_token_grounded_in_reference(t, reference_blob)]
    if matched:
        return False

    # If student uses many concrete tokens that do not appear in story content,
    # treat it as likely mismatch and force gentle correction.
    return len(content_tokens) >= 2


_STRONG_STORY_SURFACE_CUES = (
    "看到",
    "聽見",
    "聽到",
    "書裡",
    "書中",
    "故事",
    "一開始",
    "後來",
    "接著",
    "最後",
)


def _has_strong_story_surface_cues(text: str) -> bool:
    t = _normalize_match_text(text)
    return any(c in t for c in _STRONG_STORY_SURFACE_CUES)


def _eligible_for_grounding_overlap_check(
    student_text: str, book_pack: Optional[dict[str, Any]]
) -> bool:
    if looks_story_related_to_book(student_text, book_pack):
        return True
    return _has_strong_story_surface_cues(student_text)


def _split_story_grounding_clauses(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    # Treat "，然後…" as a new clause so tails are checked even without "。"
    marked = re.sub(
        r"(?<![。！？；\n])，(?=然後|接著|另外|結果)",
        "。",
        raw,
    )
    parts = re.split(r"[。！？；\n]+", marked)
    return [p.strip() for p in parts if p.strip()]


def _clause_looks_ungrounded_vs_reference(clause: str, reference_blob: str) -> bool:
    """Per-clause CJK grounding so a correct quote does not excuse a fabricated tail."""
    c = (clause or "").strip()
    if len(c) < 3:
        return False
    c_norm = _strip_story_framing_for_grounding(c)
    if _has_unsupported_event_keyword(c_norm, reference_blob):
        return True
    if _has_unsupported_action_event_claim(c_norm, reference_blob):
        return True
    tokens = _extract_cjk_tokens(c_norm)
    content_tokens = [t for t in tokens if t not in _COMMON_STORY_ANCHORS]
    if not content_tokens:
        return False
    matched = [t for t in content_tokens if _cjk_token_grounded_in_reference(t, reference_blob)]
    if matched:
        # At least one clause token is grounded in the book → treat the whole
        # clause as acceptable. Students routinely paraphrase with words that
        # don't appear verbatim in the reference blob.
        return False
    unmatched = [t for t in content_tokens if not _cjk_token_grounded_in_reference(t, reference_blob)]
    if not unmatched:
        return False
    max_u = max(len(x) for x in unmatched)
    return max_u >= 3


def looks_likely_ungrounded_in_book(
    student_text: str,
    book_pack: Optional[dict[str, Any]],
    stage: str = "O",
) -> bool:
    """
    Student writes as if describing the story (or quotes book-like scenes), but
    some concrete CJK runs are not supported by key_events/excerpts — including
    a correct quote followed by a fabricated tail sentence.

    Skips obviously off-topic daily-life lines. Uses per-clause checks so one
    matched phrase does not excuse the rest of the draft.

    D (Decisional) stage is exempt: drafts mix real-life plans with optional
    story callbacks; heuristic story-grounding yields false positives and must
    not drive “align to textbook” feedback (see `_genai_feedback` in routes).
    """
    if (stage or "O").strip().upper() == "D":
        return False

    text = (student_text or "").strip()
    if len(text) >= 3 and looks_likely_latin_hallucination(text, book_pack):
        return True
    if looks_likely_factual_mismatch(student_text, book_pack):
        return True

    if len(text) < 4:
        return False
    if looks_obviously_offtopic(text, book_pack):
        return False

    reference_blob = _extract_story_reference_blob(book_pack)
    if not reference_blob:
        return False
    if not _eligible_for_grounding_overlap_check(text, book_pack):
        return False

    for clause in _split_story_grounding_clauses(text):
        if _clause_looks_ungrounded_vs_reference(clause, reference_blob):
            return True

    tokens = _extract_cjk_tokens(text)
    if not tokens:
        return False
    content_tokens = [t for t in tokens if t not in _COMMON_STORY_ANCHORS]
    if len(content_tokens) < 2:
        return False

    matched = [t for t in content_tokens if _cjk_token_grounded_in_reference(t, reference_blob)]
    if matched:
        return False

    return True


def _looks_generic_question(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    return any(re.search(p, s) for p in _GENERIC_Q_PATTERNS)


def _stage_safe_fallback_question(stage: str, student_text: Optional[str] = None) -> str:
    s = (stage or "O").strip().upper()
    anchor = _extract_anchor(student_text or "")
    if _anchor_is_daily_life(anchor):
        anchor = ""

    if s == "R":
        if anchor:
            return _one_question(f"你剛剛提到{anchor}，那一刻你最明顯的感覺是什麼")
        return _one_question("故事裡哪一幕最讓你有感覺")
    if s == "I":
        if anchor:
            return _one_question(f"你剛剛提到{anchor}，你覺得這件事在提醒我們什麼")
        return _one_question("根據故事裡發生的事，你覺得它想提醒我們什麼")
    if s == "D":
        if anchor:
            return _one_question(f"下次遇到像{anchor}這樣的情況，你會先做哪一個小動作")
        return _one_question("下次遇到類似情況，你會先做哪一個小動作")
    if anchor:
        return _one_question(f"你剛剛提到{anchor}，接著是哪一件事讓情況開始改變")
    return _one_question("接著發生了什麼")


def build_orid_checker_prompts(
    *,
    student_text: str,
    book_pack: Optional[dict[str, Any]],
    stage: Stage,
    message_history: Optional[list[str]] = None,
    max_history: int = 6,
) -> Tuple[str, str]:
    """
    Checker responsibilities:
    1) Detect unsafe language.
    2) Detect off-topic.
    3) Produce ONE narrow, stage-appropriate, book-anchored next question.
    """
    stage = (stage or "O").strip().upper()
    if stage not in {"O", "R", "I", "D"}:
        stage = "O"

    book_context = build_book_context_block(book_pack, max_events=6, max_chars=1200)

    history = message_history or []
    history = [str(x).strip() for x in history if str(x).strip()]
    history = history[-max_history:]

    sys = f"""
你是「兒童閱讀對話的安全與引導檢查器（ORID Checker）」。
你只能根據 BOOK_CONTEXT 判斷與提問，不可編造故事細節或書外資訊。

你的工作有三件：
(1) 偵測學生訊息是否含不友善用語（辱罵、人身攻擊、歧視、威脅、性暗示等）。
(2) 偵測是否離題。
(3) 產生一個「下一小步」的問題（suggested_question）。

目前 ORID 階段：{stage}
- O：只問故事中的角色、事件、順序、轉折，不問感受、道理、行動
- R：問感受＋原因，而且原因要連回故事事件
- I：問道理／提醒＋理由，而且理由要連回故事
- D：問下次可做的小行動，而且要具體、貼近日常

判斷離題的重要原則：
- 只要學生有提到書中角色、事件、畫面、主題，或對這些內容做簡單評論，都不算離題。
- 例如「他很小氣」「這樣不公平」「他後來有改變」都不算離題。
- 像「我今天中午吃排骨便當」「我昨天去打球」這種明顯和故事無關的生活句子，才算 off_topic=true。
- 不要因為學生只說一小句就當成離題；先看它有沒有碰到故事線索。

suggested_question 的重要原則：
- 要問「下一小步」，不是退回大題。
- 若學生已經說到一個事件，不要又問「故事發生了什麼」。
- 若學生已經說到感受，不要又問「你有什麼感覺」；要問原因或是哪個畫面。
- 若學生已經說到道理，不要又問「提醒我們什麼」；要問理由或故事根據。
- 若學生已經說到行動，不要又問「你會怎麼做」；要問第一步、對誰、什麼時候做。
- 若學生明顯離題，不要重複他的生活瑣事細節；直接用書裡角色或事件把他拉回來。
- suggested_question 只能有一個問號（？）。

輸出必須是純 JSON，不要任何多餘文字、不要 code block。
JSON schema（欄位不可少）：
{{
  "unsafe_language": boolean,
  "unsafe_reason": string,
  "off_topic": boolean,
  "reason": string,
  "suggested_question": string
}}

若 unsafe_language=true：
- unsafe_reason 用很短一句話，例如：語氣不友善 / 包含人身攻擊
- reason 填相同意思
- suggested_question 仍要給，但要溫和把學生拉回書與本階段方向，不可重複學生的髒話

若 off_topic=true：
- reason 用「離題」或「先回到故事」
- suggested_question 要用書裡角色或事件拉回，不可責備

若既不 unsafe 也不 off-topic：
- off_topic=false，reason 用「OK」或「貼近本階段」
- suggested_question 要是本階段下一個更窄的問題，不可跳階，也不可回到整體大題

BOOK_CONTEXT：
{book_context}
""".strip()

    user = f"""
學生訊息：
{student_text}

近期對話（只用來判斷是否離題與下一小步，不可編造書外資訊）：
{json.dumps(history, ensure_ascii=False)}
""".strip()

    return sys, user


def build_book_grounding_checker_prompts(
    *,
    student_text: str,
    book_pack: Optional[dict[str, Any]],
    stage: Stage,
) -> Tuple[str, str]:
    """
    LLM grounding checker:
    Decide whether the student's claim is supported by BOOK_CONTEXT facts.
    """
    stage = (stage or "O").strip().upper()
    if stage not in {"O", "R", "I", "D"}:
        stage = "O"
    book_context = build_book_context_block(book_pack, max_events=8, max_chars=1500)
    sys = f"""
你是「教材事實核對器」。
你的任務：判斷學生這句話是否可由 BOOK_CONTEXT 支持。
只允許根據 BOOK_CONTEXT 判斷，不可編造或腦補。

判斷原則（很重要）：
- O 段：最嚴格。若寫了書裡沒有的具體事件（誰做了什麼），grounded=false。
- R/I/D 段：若學生是感受、想法、行動，且沒有捏造新事件，可 grounded=true；
  但只要把「書裡沒有發生」的事件當成事實，就 grounded=false。
- 太短或資訊不足時，優先 grounded=true，reason 寫「資訊不足但未見明顯衝突」。

輸出必須是純 JSON，不要多餘文字：
{{
  "grounded": boolean,
  "reason": string,
  "unsupported_span": string
}}

欄位規範：
- reason：20 字內，簡短說明（例：教材可支持 / 疑似新增書外事件）
- unsupported_span：若 grounded=false，填學生原句中的關鍵片段；否則填空字串。

目前階段：{stage}
BOOK_CONTEXT：
{book_context}
""".strip()
    user = f"學生句子：\n{student_text}"
    return sys, user


def parse_book_grounding_checker_json(raw: str) -> Dict[str, Any]:
    if raw is None:
        return {}
    s = str(raw).strip()
    if not s:
        return {}
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        m = _JSON_RE.search(s)
        if not m:
            return {}
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}


def parse_orid_checker_json(raw: str) -> Dict[str, Any]:
    if raw is None:
        return {}
    s = str(raw).strip()
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        m = _JSON_RE.search(s)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}


def clamp_checker_output(
    obj: Dict[str, Any],
    *,
    stage: Optional[str] = None,
    student_text: Optional[str] = None,
) -> Dict[str, Any]:
    unsafe_language = bool(obj.get("unsafe_language", False))
    off_topic = bool(obj.get("off_topic", False))

    unsafe_reason = obj.get("unsafe_reason", "")
    reason = obj.get("reason", "")
    suggested_question = obj.get("suggested_question", "")

    if not isinstance(unsafe_reason, str):
        unsafe_reason = ""
    if not isinstance(reason, str):
        reason = ""
    if not isinstance(suggested_question, str):
        suggested_question = ""

    unsafe_reason = unsafe_reason.strip()[:80]
    reason = reason.strip()[:80]
    suggested_question = suggested_question.strip()

    stage_norm = (stage or "O").strip().upper()
    if stage_norm not in {"O", "R", "I", "D"}:
        stage_norm = "O"

    if student_text and _looks_unsafe_by_structure(student_text):
        unsafe_language = True
        if not unsafe_reason:
            unsafe_reason = "語氣不友善"

    if unsafe_language:
        off_topic = False
        if not unsafe_reason:
            unsafe_reason = "語氣不友善"
        if not reason or ("描述故事" in reason):
            reason = unsafe_reason
        if not suggested_question or _looks_generic_question(suggested_question):
            suggested_question = _stage_safe_fallback_question(stage_norm, student_text)
    else:
        if off_topic:
            if not reason:
                reason = "先回到故事"
            if not suggested_question or _looks_generic_question(suggested_question):
                suggested_question = _stage_safe_fallback_question(stage_norm, None)
        else:
            if not reason:
                reason = "OK"
            if not suggested_question:
                suggested_question = _stage_safe_fallback_question(stage_norm, student_text)

    suggested_question = (
        _one_question(suggested_question)
        if suggested_question
        else _stage_safe_fallback_question(stage_norm, student_text)
    )

    return {
        "unsafe_language": bool(unsafe_language),
        "unsafe_reason": unsafe_reason,
        "off_topic": bool(off_topic),
        "reason": reason,
        "suggested_question": suggested_question,
    }


def quick_unsafe_check(student_text: str) -> bool:
    return _looks_unsafe_by_structure(student_text)