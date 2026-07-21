from __future__ import annotations

from typing import Any, Optional
import re


_ATTACK_PATTERNS = [
    r"(你|妳|他|她|你們|妳們)\s*(是|很|超|真|也太)?\s*[^ \n]{0,4}(笨|蠢|爛|噁|討厭|白痴|白癡|智障|低能|廢物)",
    r"(你|妳|他|她)\s*(去|給我去)\s*(死|滾)",
]
_PROFANITY_MIN = [
    "幹", "靠北", "操", "媽的", "他媽", "白痴", "白癡", "智障", "廢物", "去死",
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
    "吃",
    "咬",
]
_ACTION_EVENT_VERB_RE = r"(?:打|揍|毆|踢|砍|殺|欺負|霸凌|吃|咬)"
# Verb + nearby object that is already in the book → treat as paraphrase, not fabrication.
_BOOK_ACTION_PARAPHRASE_ALLOW: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("砍", ("樹", "柿子樹", "樹樁", "樹椿", "光光", "砍掉", "砍光")),
    ("吃", ("柿子", "大口", "面前", "甜柿")),
)
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


def looks_unsafe_by_structure(text: str) -> bool:
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


def normalize_match_text(text: str) -> str:
    t = re.sub(r"[\s「」『』\"'，。！？：；、（）()\[\]{}、]+", "", (text or "").strip())
    return t.replace("\u4f54", "\u5360")


def extract_book_terms(book_pack: Optional[dict[str, Any]]) -> set[str]:
    terms: set[str] = set()
    if not isinstance(book_pack, dict):
        return terms

    def add_term(value: Any) -> None:
        s = str(value or "").strip()
        if not s:
            return
        s_clean = normalize_match_text(s)
        if 2 <= len(s_clean) <= 10:
            terms.add(s_clean)
        for token in re.findall(r"[一-龥A-Za-z]{2,8}", s):
            token = normalize_match_text(token)
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
    text_norm = normalize_match_text(student_text)
    if not text_norm:
        return False

    book_terms = extract_book_terms(book_pack)
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
    text_norm = normalize_match_text(student_text)
    if not text_norm:
        return False
    if looks_story_related_to_book(student_text, book_pack):
        return False

    if text_norm.startswith("我今天") or text_norm.startswith("我昨天") or text_norm.startswith("我剛剛"):
        return True

    if any(k in text_norm for k in _DAILY_LIFE_KEYWORDS):
        return True

    if re.fullmatch(r"[A-Za-z0-9_]{2,40}", text_norm):
        return True

    if re.search(r"(唱歌|去唱|ktv|nba|wnba|夜店|酒吧)", text_norm, flags=re.IGNORECASE):
        return True

    if (not re.search(r"[一-龥]", student_text or "")) and re.fullmatch(r"[A-Za-z0-9_\-\+\=\.\, ]{4,60}", student_text.strip()):
        return True

    daily_patterns = [
        r"我(要|想|去|在).{0,8}(吃|買|玩|睡|上課|下課|回家)",
        r"(午餐|早餐|晚餐|便當|手機|遊戲|天氣)",
    ]
    return any(re.search(p, text_norm) for p in daily_patterns)


def extract_story_reference_blob(book_pack: Optional[dict[str, Any]]) -> str:
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
    return normalize_match_text(" ".join(parts))


def strip_story_framing_for_grounding(text: str) -> str:
    """
    Remove common student framing words before grounding token checks.
    Otherwise "故事裡先發生了爺爺..." gets greedily tokenized into unsupported
    chunks like "故事裡先發".
    """
    t = normalize_match_text(text)
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


def _action_span_supported_by_book(span: str, verb: str, reference_blob: str) -> bool:
    """True when the action span is literally in the book or a known in-book paraphrase."""
    s = normalize_match_text(span)
    if not s or not reference_blob:
        return False
    if s in reference_blob:
        return True
    # Expanding windows around the verb: 「砍樹」「大口吃」等原文片段
    m = re.search(re.escape(verb), s)
    if m:
        i = m.start()
        vlen = len(verb)
        for left in range(0, 5):
            for right in range(0, 5):
                frag = s[max(0, i - left) : min(len(s), i + vlen + right)]
                if len(frag) >= 2 and frag in reference_blob:
                    return True
    # Semantic paraphrase allowlist (e.g. 樹都砍光光 ≈ 砍樹)
    for allow_verb, cues in _BOOK_ACTION_PARAPHRASE_ALLOW:
        if verb != allow_verb:
            continue
        if allow_verb not in reference_blob:
            continue
        if any(c in s for c in cues) and any(
            c in reference_blob for c in cues if c not in ("光光", "砍掉", "砍光", "大口", "面前")
        ):
            return True
        # 砍 + 樹* : book has 砍 and 樹
        if allow_verb == "砍" and ("樹" in s) and ("樹" in reference_blob):
            return True
        if allow_verb == "吃" and ("柿子" in s or "大口" in s) and (
            "柿子" in reference_blob or "大口吃" in reference_blob or "吃" in reference_blob
        ):
            return True
    return False


def _has_unsupported_event_keyword(text_norm: str, reference_blob: str) -> bool:
    if not text_norm or not reference_blob:
        return False
    for kw in _UNSUPPORTED_EVENT_KEYWORDS:
        k = normalize_match_text(kw)
        if k and k in text_norm and k not in reference_blob:
            return True
    return False


def _has_unsupported_action_event_claim(text_norm: str, reference_blob: str) -> bool:
    if not text_norm or not reference_blob:
        return False
    spans = re.findall(rf"[一-龥]{{0,4}}{_ACTION_EVENT_VERB_RE}[一-龥]{{0,4}}", text_norm)
    for sp in spans:
        s = normalize_match_text(sp)
        if len(s) < 3:
            continue
        m = re.search(_ACTION_EVENT_VERB_RE, s)
        if not m:
            continue
        verb = m.group(0)
        if _action_span_supported_by_book(s, verb, reference_blob):
            continue
        if any(k in s for k in _ACTION_EVENT_KEYWORDS):
            i = m.start()
            left = s[max(0, i - 2) : i + 1]
            right = s[i : min(len(s), i + 3)]
            if left and right and left not in reference_blob and right not in reference_blob:
                return True
    return False


def extract_unsupported_action_phrase(
    student_text: str, book_pack: Optional[dict[str, Any]]
) -> str:
    """Return a short fabricated action phrase (e.g. 爺爺打奶奶) for student-facing feedback."""
    reference_blob = extract_story_reference_blob(book_pack)
    if not reference_blob:
        return ""
    text_norm = normalize_match_text(student_text)
    spans = re.findall(rf"[一-龥]{{0,4}}{_ACTION_EVENT_VERB_RE}[一-龥]{{0,4}}", text_norm)
    for sp in spans:
        s = normalize_match_text(sp)
        if len(s) < 3:
            continue
        m = re.search(_ACTION_EVENT_VERB_RE, s)
        if not m:
            continue
        verb = m.group(0)
        if _action_span_supported_by_book(s, verb, reference_blob):
            continue
        i = m.start()
        left = s[max(0, i - 2) : i + 1]
        right = s[i : min(len(s), i + 3)]
        if left and right and left not in reference_blob and right not in reference_blob:
            phrase = re.sub(r"^(因為|所以|為了)", "", sp).strip() or sp.strip()
            return phrase
    return ""


def extract_wrong_concrete_noun(
    student_text: str, book_pack: Optional[dict[str, Any]]
) -> str:
    """Return a short wrong noun (e.g. 地瓜) when student cites a concrete detail not in the book."""
    reference_blob = extract_story_reference_blob(book_pack)
    if not reference_blob:
        return ""
    text_norm = normalize_match_text(student_text)
    for pattern in (r"吃([一-龥]{2,4})", r"拿([一-龥]{2,4})", r"用([一-龥]{2,4})"):
        m = re.search(pattern, text_norm)
        if not m:
            continue
        noun = m.group(1)
        if not noun or noun in reference_blob or noun in _COMMON_STORY_ANCHORS:
            continue
        # Avoid swallowing following verbs/clauses: 吃看到奶奶
        if noun.startswith(("看", "到", "了", "完", "得", "著", "过", "過")):
            continue
        if any(v in noun for v in ("打", "砍", "殺", "踢", "揍")):
            continue
        return noun
    return ""


def book_contrast_noun_for(
    wrong_noun: str, book_pack: Optional[dict[str, Any]]
) -> str:
    """Pick a book-supported noun to contrast with a wrong student noun (e.g. 柿子 vs 地瓜)."""
    reference_blob = extract_story_reference_blob(book_pack)
    wrong = normalize_match_text(wrong_noun or "")
    if not wrong or not reference_blob:
        return ""

    char_terms: set[str] = set()
    skip_aliases = {"爺爺", "奶奶", "孩子", "小朋友", "大家", "一起", "阿松"}
    if isinstance(book_pack, dict):
        for item in book_pack.get("characters") or []:
            if isinstance(item, dict):
                name = normalize_match_text(str(item.get("name") or ""))
                if name:
                    char_terms.add(name)

    def _usable(term: str, *, allow_story_anchors: bool = False) -> bool:
        anchor_block = set() if allow_story_anchors else _COMMON_STORY_ANCHORS
        return (
            2 <= len(term) <= 3
            and term != wrong
            and term in reference_blob
            and term not in anchor_block
            and term not in char_terms
            and term not in skip_aliases
            and wrong not in term
            and not any(cn == term or (len(cn) >= 3 and cn in term) for cn in char_terms)
        )

    title_theme_candidates: list[str] = []
    if isinstance(book_pack, dict):
        title = normalize_match_text(str(book_pack.get("book_title") or ""))
        title_focus = title.split("的")[-1] if "的" in title else title
        if len(title_focus) < 2:
            title_focus = title
        for cand in re.findall(r"[一-龥]{2}", title_focus):
            if _usable(cand, allow_story_anchors=True):
                title_theme_candidates.append(cand)

    if title_theme_candidates:
        uniq = list(dict.fromkeys(title_theme_candidates))
        uniq.sort(key=lambda t: (reference_blob.count(t), -len(t)), reverse=True)
        return uniq[0]

    book_terms = extract_book_terms(book_pack)
    contras = [t for t in book_terms if _usable(t)]
    if not contras:
        return ""
    contras.sort(key=lambda t: (reference_blob.count(t), -len(t)), reverse=True)
    return contras[0]


def _cjk_token_grounded_in_reference(token: str, reference_blob: str) -> bool:
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
    raw = re.findall(r"[一-龥]{2,5}", normalize_match_text(text))
    seen: set[str] = set()
    out: list[str] = []
    for t in raw:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def looks_likely_latin_hallucination(
    student_text: str, book_pack: Optional[dict[str, Any]]
) -> bool:
    s = (student_text or "").strip()
    if not s or not isinstance(book_pack, dict):
        return False
    if not re.search(r"[A-Za-z]{3,}", s):
        return False
    reference_blob = extract_story_reference_blob(book_pack)
    if not reference_blob:
        return False
    blob_lower = reference_blob.lower()
    blob_compact = normalize_match_text(reference_blob).lower()
    for m in re.finditer(r"[A-Za-z]{3,}", s):
        w = m.group(0).lower()
        if w in _LATIN_HALLUC_ALLOWLIST:
            continue
        if w in blob_lower or w in blob_compact:
            continue
        return True
    return False


def looks_likely_factual_mismatch(student_text: str, book_pack: Optional[dict[str, Any]]) -> bool:
    text = (student_text or "").strip()
    if len(text) < 4:
        return False
    if not looks_story_related_to_book(text, book_pack):
        return False
    if looks_obviously_offtopic(text, book_pack):
        return False

    text_norm = normalize_match_text(text)
    if any(k in text_norm for k in _ABSURD_MISMATCH_KEYWORDS):
        return True

    reference_blob = extract_story_reference_blob(book_pack)
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
    return len(content_tokens) >= 2


def _has_strong_story_surface_cues(text: str) -> bool:
    t = normalize_match_text(text)
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
    marked = re.sub(
        r"(?<![。！？；\n])，(?=然後|接著|另外|結果)",
        "。",
        raw,
    )
    parts = re.split(r"[。！？；\n]+", marked)
    return [p.strip() for p in parts if p.strip()]


def _clause_looks_ungrounded_vs_reference(clause: str, reference_blob: str) -> bool:
    c = (clause or "").strip()
    if len(c) < 3:
        return False
    c_norm = strip_story_framing_for_grounding(c)
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

    reference_blob = extract_story_reference_blob(book_pack)
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


_ABSENCE_CLAIM_MARKERS = (
    "書裡沒有",
    "書中沒有",
    "沒有提到",
    "沒提到",
    "不在書裡",
    "書裡沒提到",
)
# Canonically present gifts/objects in week-1 story (never "not in book")
_WEEK1_CANONICAL_GIVEABLES = (
    "柿子蒂",
    "樹枝",
    "葉子",
    "枯葉",
    "種子",
)


def _book_reference_mentions(book_pack: Optional[dict[str, Any]], term: str) -> bool:
    if not isinstance(book_pack, dict) or not term:
        return False
    blob = extract_story_reference_blob(book_pack)
    return term in (blob or "")


def scrub_false_book_absence_claims(
    *,
    missing: list[str],
    suggestions: list[str],
    book_pack: Optional[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Drop / rewrite feedback that falsely says canonical book items are absent.

    Example false claim: 「書裡沒有提到爺爺分享樹枝和柿子蒂」— both items are in-book.
    """
    if not missing:
        return missing, suggestions
    m0 = (missing[0] or "").strip()
    if not m0:
        return missing, suggestions
    if not any(tok in m0 for tok in _ABSENCE_CLAIM_MARKERS):
        return missing, suggestions

    hit_terms = [
        t for t in _WEEK1_CANONICAL_GIVEABLES if t in m0 and _book_reference_mentions(book_pack, t)
    ]
    if hit_terms:
        soft = (
            "書裡確實有阿松爺爺把柿子蒂、葉子或樹枝給哎唷奶奶和小朋友；"
            "你可以再說清楚：甜柿子當時還多半藏著，他先給出去的比較像蒂／葉子／樹枝。"
        )
        sug = "試著補一句：他給了柿子蒂或樹枝之後，甜柿子怎麼了？（例如藏進倉庫）"
        return [soft], [sug]

    # False denial of tree-cutting paraphrases (砍光光 / 樹都砍掉 ≈ 書裡的砍樹)
    cut_paraphrase_cues = ("砍光", "砍掉", "砍樹", "樹都砍", "把自己的樹", "把樹砍", "樹砍")
    if any(c in m0 for c in cut_paraphrase_cues) and _book_reference_mentions(
        book_pack, "砍"
    ) and _book_reference_mentions(book_pack, "樹"):
        return [], suggestions

    return missing, suggestions
