from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import json
import re

from .shared import build_book_context_block

Stage = str  # "O" | "R" | "I" | "D"


# ----------------------------
# Lightweight unsafe heuristics (not a blacklist)
# - Focus on "attack structure": "你/妳 + 是/很/超 + 貶損詞"
# - Also catch common profanity patterns without enumerating tons of words
# ----------------------------
_ATTACK_PATTERNS = [
    r"(你|妳|他|她|你們|妳們)\s*(是|很|超|真|也太)\s*[^ \n]{0,4}(笨|蠢|爛|噁|討厭|白痴|智障)",
    r"(你|妳|他|她)\s*(去|給我去)\s*(死|滾)",
]
# A small set of high-signal profanity tokens (kept minimal; not a big blacklist)
_PROFANITY_MIN = [
    "幹", "靠北", "操", "媽的", "他媽", "傻逼", "白痴", "智障", "廢物"
]

_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _looks_unsafe_by_structure(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    t_nospace = re.sub(r"\s+", "", t)
    for p in _ATTACK_PATTERNS:
        if re.search(p, t_nospace):
            return True
    # minimal profanity signal (not exhaustive)
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


def _stage_safe_fallback_question(stage: str) -> str:
    s = (stage or "O").strip().upper()
    if s == "R":
        return _one_question("把故事裡那一刻說清楚後，你最強烈的感覺是什麼")
    if s == "I":
        return _one_question("根據故事發生的事，你覺得它想提醒我們什麼")
    if s == "D":
        return _one_question("如果下次遇到類似情況，你會先做哪一個小行動")
    return _one_question("你先用1–2句話說說故事發生了什麼")


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
    1) Detect unsafe language (insult/harassment/hate/threat/sexual) -> unsafe_language=true
    2) Detect off-topic -> off_topic=true
    3) Produce ONE book-anchored question suited for current stage (O/R/I/D)
    Output must be strict JSON.
    """
    stage = (stage or "O").strip().upper()
    if stage not in {"O", "R", "I", "D"}:
        stage = "O"

    book_context = build_book_context_block(book_pack, max_events=6, max_chars=1200)

    history = message_history or []
    history = [str(x).strip() for x in history if str(x).strip()]
    history = history[-max_history:]

    # NOTE: The checker must not do "emotion guessing" like "你有情緒"
    # It should be: boundary + pull back to task/story, and provide stage-appropriate question.
    sys = f"""
你是「兒童閱讀對話的安全與引導檢查器（ORID Checker）」。
你只允許根據 BOOK_CONTEXT 判斷與提問，不可編造故事細節或書外資訊。

你要做三件事：
(1) 偵測學生訊息是否含不友善用語（辱罵、人身攻擊、歧視、威脅、性暗示等）。只要有，unsafe_language=true。
(2) 偵測是否離題（與書或本階段任務無關）。離題就 off_topic=true。
(3) 產生一個「拉回故事」且符合目前 ORID 階段的問題（suggested_question）。

目前 ORID 階段：{stage}
- O：問「故事發生什麼/誰做什麼/先後順序」，不能問感受或道理或行動
- R：問「感受＋原因（連回故事事件）」，不能跳道理或行動
- I：問「故事提醒的道理/價值＋理由（連回故事）」不能跳行動
- D：問「下次可做的小行動（具體）」要貼近日常

輸出必須是「純 JSON」，不要任何多餘文字、不要 code block。
JSON schema（欄位不可少）：
{{
  "unsafe_language": boolean,
  "unsafe_reason": string,
  "off_topic": boolean,
  "reason": string,
  "suggested_question": string
}}

重要規則：
- 你不能寫「你有情緒」「你不耐煩」這種推測心理狀態的句子。
- suggested_question 必須只出現一個問號（？）；若沒有問號請在句尾加「？」；若有多個只保留第一個。
- 若 unsafe_language=true：
  - unsafe_reason 用很短一句話，例如「語氣不友善」或「包含人身攻擊」。
  - reason 也填入同樣意思（不要寫「尚未描述故事」）。
  - suggested_question 仍要給：用溫和方式拉回書與本階段任務，且不要重複學生的髒話/辱罵字。
- 若 off_topic=true：
  - reason 用「離題」或「先回到故事」等短句。
  - suggested_question 要用 BOOK_CONTEXT 的事件/角色拉回，不要指責學生。
- 若 neither unsafe nor off-topic：
  - off_topic=false，reason 用「OK」或「貼近本階段」。
  - suggested_question 仍要是本階段下一個引導問題（不要跳階）。

BOOK_CONTEXT：
{book_context}
""".strip()

    user = f"""
學生訊息：
{student_text}

近期對話（用來判斷是否離題，不要用來編造書外資訊）：
{json.dumps(history, ensure_ascii=False)}
""".strip()

    return sys, user


def parse_orid_checker_json(raw: str) -> Dict[str, Any]:
    """Robust JSON extractor."""
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


def clamp_checker_output(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure stable types + required fields.
    Also apply a lightweight post-check so obvious insults never slip through.
    """
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

    # --- Post safety reinforcement (structure-based, minimal tokens) ---
    # If model forgot to flag, but text is clearly abusive, force unsafe=true.
    # NOTE: We rely on the model for semantics; this just catches high-signal misses.
    # The actual student text isn't passed here, so we can only stabilize reasons/fields.
    # We keep this block for consistency and future extension if you later pass student_text in clamp.
    if unsafe_language:
        if not unsafe_reason:
            unsafe_reason = "語氣不友善"
        # reason should not be "尚未描述故事" when unsafe
        if not reason or ("描述故事" in reason):
            reason = unsafe_reason
        # suggested_question must exist even when unsafe
        if not suggested_question:
            suggested_question = _stage_safe_fallback_question("O")  # default safe pull-back
    else:
        # If not unsafe, keep reasons short and aligned
        if off_topic:
            if not reason:
                reason = "先回到故事"
        else:
            if not reason:
                reason = "OK"

    # Always enforce one-question rule
    suggested_question = _one_question(suggested_question) if suggested_question else _stage_safe_fallback_question("O")

    return {
        "unsafe_language": bool(unsafe_language),
        "unsafe_reason": unsafe_reason,
        "off_topic": bool(off_topic),
        "reason": reason,
        "suggested_question": suggested_question,
    }


# ----------------------------
# Optional: helper you can use in routes if you want extra safety
# (Not required right now; kept here for easy import later)
# ----------------------------
def quick_unsafe_check(student_text: str) -> bool:
    """Structure-based quick check; can be used as a pre-check before calling LLM."""
    return _looks_unsafe_by_structure(student_text)