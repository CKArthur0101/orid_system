from __future__ import annotations

from uuid import UUID
from typing import Optional, Any, Tuple, List, Dict
import os
import re
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from pydantic import BaseModel, Field
from openai import AsyncOpenAI, BadRequestError

from app.database import get_async_session, User
from app.users import current_active_user
from app.models import Reading, OridSession, OridMessage, OridWriting
from app.schemas import (
    ReadingCreate, ReadingRead,
    OridSessionCreate, OridSessionRead,
    OridChatRequest, OridChatResponse,
    OridWritingCreate, OridWritingUpdate, OridWritingRead,
    OridMessageRead,
)

router = APIRouter(tags=["orid"])

# ----------------------------
# ✅ Prompt bank & Checker (direct import)
# ----------------------------
PROMPTS_OK = True
PROMPTS_IMPORT_ERROR: Optional[str] = None
CHECKER_OK = True
CHECKER_IMPORT_ERROR: Optional[str] = None

from app.prompts.shared import build_book_context_block
from app.prompts.orid_chat import build_orid_chat_system_prompt
from app.prompts.writing_feedback import build_genai_feedback_prompts
from app.prompts.writing_assist import (
    ASSIST_TEXT_SPLIT,
    build_writing_d1_prompts,
    build_writing_d2_prompts,
)
from app.prompts.orid_checker import (
    build_orid_checker_prompts,
    parse_orid_checker_json,
    clamp_checker_output,
)
from app.services.safety import check_safety


# ----------------------------
# OpenAI settings (from env)
# ----------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.1-chat-latest")

OPENAI_MAX_COMPLETION_TOKENS = int(
    os.getenv("OPENAI_MAX_COMPLETION_TOKENS")
    or os.getenv("OPENAI_MAX_TOKENS")
    or "260"
)

OPENAI_TEMPERATURE_RAW = os.getenv("OPENAI_TEMPERATURE")
OPENAI_TEMPERATURE: Optional[float] = None
if OPENAI_TEMPERATURE_RAW:
    try:
        OPENAI_TEMPERATURE = float(OPENAI_TEMPERATURE_RAW)
    except Exception:
        OPENAI_TEMPERATURE = None

# ✅ 不要在 import 階段把整個後端炸掉：key 沒設就讓需要 LLM 的端點回 503
OPENAI_ENABLED = bool((OPENAI_API_KEY or "").strip())
client: Optional[AsyncOpenAI] = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_ENABLED else None


async def _chat_completion(
    messages: List[Dict[str, str]],
    *,
    max_completion_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    response_format: Optional[Dict[str, Any]] = None,
) -> str:
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY 未設定，LLM 功能暫不可用（但登入/Docs 應可正常）。",
        )

    kwargs: Dict[str, Any] = {"model": OPENAI_MODEL, "messages": messages}
    if max_completion_tokens is not None:
        kwargs["max_completion_tokens"] = max_completion_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    if response_format is not None:
        kwargs["response_format"] = response_format

    def _content(resp: Any) -> str:
        try:
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""

    try:
        resp = await client.chat.completions.create(**kwargs)
        return _content(resp)
    except BadRequestError as e:
        msg = str(e)
        if "temperature" in msg and ("unsupported" in msg or "Only the default" in msg):
            kwargs.pop("temperature", None)
            resp = await client.chat.completions.create(**kwargs)
            return _content(resp)
        if "max_completion_tokens" in msg and "unsupported" in msg:
            kwargs.pop("max_completion_tokens", None)
            resp = await client.chat.completions.create(**kwargs)
            return _content(resp)
        if "response_format" in msg and "unsupported" in msg:
            kwargs.pop("response_format", None)
            resp = await client.chat.completions.create(**kwargs)
            return _content(resp)
        raise


# ----------------------------
# ORID runtime knobs
# ----------------------------
def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return default
    return v in {"1", "true", "yes", "y", "on"}


ORID_DEMO_MODE = _env_bool("ORID_DEMO_MODE", True)
ORID_HISTORY_LIMIT = int(os.getenv("ORID_HISTORY_LIMIT", "10"))

ORID_REQUIRED_PASS_DEFAULT = int(os.getenv("ORID_REQUIRED_PASS", "1" if ORID_DEMO_MODE else "2"))
ORID_REQUIRED_PASS_D = int(os.getenv("ORID_REQUIRED_PASS_D", "1"))

# checker debug switch
ORID_CHECKER_DEBUG = _env_bool("ORID_CHECKER_DEBUG", False)

# ----------------------------
# ORID stage helpers
# ----------------------------
STAGE_ORDER = ["O", "R", "I", "D"]
STAGE_NAME = {
    "O": "O（客觀）",
    "R": "R（感受）",
    "I": "I（意義）",
    "D": "D（行動）",
}

# ✅ 改成更像聊天的轉場（不要出現「我們進入 R」）
STAGE_TRANSITION_PREFIX = {
    "O": "好，我們先把故事說清楚一點。",
    "R": "懂了～那你心裡的感覺是什麼呢。",
    "I": "好，那你覺得這件事在提醒我們什麼。",
    "D": "最後想一下，如果換成你，下次你會怎麼做。",
}


def next_stage(stage: str) -> str:
    if stage not in STAGE_ORDER:
        return "O"
    idx = STAGE_ORDER.index(stage)
    return STAGE_ORDER[min(idx + 1, len(STAGE_ORDER) - 1)]


def _sanitize_one_question(text: str) -> str:
    """Keep only ONE question mark (？). Convert ? -> ？ and cut after first ？."""
    t = (text or "").strip().replace("?", "？")
    if not t:
        return "你可以再說清楚一點嗎？"
    if "？" not in t:
        return t + "？"
    # keep only first question
    first = t.split("？", 1)[0].strip()
    return first + "？"


def ai_prompt_by_stage(stage: str) -> str:
    # ✅ 全部保證只有一個問號
    if stage == "O":
        return _sanitize_one_question("你先用 1–2 句話說說故事發生了什麼（先講事實，不要加感想）")
    if stage == "R":
        return _sanitize_one_question("如果你在現場，你最強烈的感覺是哪一種（失望/生氣/緊張/期待…）")
    if stage == "I":
        return _sanitize_one_question("你覺得這個故事最想提醒我們的一個道理是什麼")
    return _sanitize_one_question("下次遇到想獨占或誤會別人的情況，你願意先做哪一個小行動")


def _two_sentence_ack_then_question(ack: str, question: str) -> str:
    a = (ack or "").strip()
    if not a:
        a = "我有聽到你說的。"
    if not a.endswith(("。", "！", "～")):
        a += "。"
    q = _sanitize_one_question(question)
    return f"{a}{q}"


# ----------------------------
# PASS-tag parsing
# ----------------------------
PASS_RE = re.compile(r"【PASS:(true|false)】", re.IGNORECASE)
NEXT_RE = re.compile(r"【NEXT:([ORID])】", re.IGNORECASE)
REASON_RE = re.compile(r"【REASON:(.*?)】")


def parse_control_tags(text: str) -> Tuple[bool, Optional[str], Optional[str], str, bool]:
    pass_ok = False
    next_s = None
    reason = None
    has_tags = False

    m = PASS_RE.search(text)
    if m:
        has_tags = True
        pass_ok = (m.group(1).lower() == "true")

    m2 = NEXT_RE.search(text)
    if m2:
        has_tags = True
        next_s = m2.group(1).upper()

    m3 = REASON_RE.search(text)
    if m3:
        has_tags = True
        reason = m3.group(1).strip()

    clean = PASS_RE.sub("", text)
    clean = NEXT_RE.sub("", clean)
    clean = REASON_RE.sub("", clean)
    clean = clean.strip()

    return pass_ok, next_s, reason, clean, has_tags


# ----------------------------
# Week reading defaults
# ----------------------------
DEFAULT_READING_TITLE_TEMPLATE = "第 {week} 週（暫定教材）"

BOOK_PACK_BY_WEEK: dict[int, dict[str, Any]] = {
    1: {
        "schema": "book_pack_v1",
        "book_title": "阿松爺爺的柿子樹",
        "grade": "國小高年級（五、六年級）",
        "core_theme": ["分享", "誤會與衝動", "珍惜", "把好東西變成大家的好"],
        "characters": [
            {"name": "阿松爺爺", "role": "很珍惜柿子樹，但一開始太想獨占"},
            {"name": "奶奶", "role": "提醒與安撫，帶出『留種子、一起種』的轉機"},
            {"name": "孩子們", "role": "想吃柿子、也願意一起幫忙"},
        ],
        "setting": ["鄉村/果樹旁", "柿子成熟的季節"],
        "key_events": [
            "阿松爺爺覺得自家柿子很甜，捨不得分給別人。",
            "孩子們很想吃，但只能看著；阿松爺爺常常防著別人。",
            "阿松爺爺因為誤會或情緒，一時衝動做了讓自己後悔的事。",
            "奶奶提醒：柿子不只是拿來吃，也可以留下『種子』帶來新的開始。",
            "大家一起把柿子/種子好好處理、播種，阿松爺爺的想法也慢慢改變。",
        ],
        "orid_prompt_bank": {
            "O": [
                "故事裡有哪些角色，他們正在做什麼？",
                "阿松爺爺一開始對柿子是怎麼想、怎麼做的？",
                "後來發生了什麼事，讓情況開始改變？",
                "奶奶做了什麼或說了什麼，事情因此怎麼變？",
            ],
            "R": [
                "如果你是孩子們，只能看著柿子卻吃不到，你比較像哪個感覺（失望/生氣/羨慕/期待）？為什麼？",
                "如果你是阿松爺爺，你覺得他最擔心什麼？",
                "故事裡哪一個瞬間讓你心裡『卡一下』？",
                "你最同情誰，你願意替他說一句安慰的話嗎？",
                "如果這件事發生在你班上，你覺得大家心情會變成什麼樣？",
            ],
            "I": [
                "你覺得故事最想提醒我們的一個道理是什麼？再用一句話說原因。",
                "你覺得『留種子』在故事裡像在說什麼？（它可能代表什麼）",
                "你覺得分享為什麼能讓事情變好？",
                "阿松爺爺會改變的關鍵是什麼？",
                "如果把故事變成一句班級座右銘，你會寫哪一句？",
            ],
            "D": [
                "下次你也很想獨占時，你願意先做哪一個小行動讓自己冷靜（例如深呼吸、先問、先分享一點）？",
                "如果你誤會別人了，你會先做哪一步把事情問清楚、把話說好？",
                "這週你可以做一個『分享』小行動嗎，你打算做什麼？",
                "當你生氣想衝動做事時，你會用什麼方法讓自己先停一下？",
                "如果你是阿松爺爺，你會怎麼跟孩子們和好，你會做什麼？",
            ],
        },
        "writing_guide": {
            "O": "客觀：角色+事件順序，不加入評價。",
            "R": "感受：情緒詞+原因（因為…所以…）。",
            "I": "意義：學到的道理/價值+理由。",
            "D": "行動：下次我會…（可操作、可做到）。",
        },
    }
}


def _default_reading_content_for_week(week: int) -> str:
    pack = BOOK_PACK_BY_WEEK.get(week)
    if pack:
        return json.dumps(pack, ensure_ascii=False)
    return "先用測試文字，之後再換正式教材。"


DEFAULT_READING_CONTENT_BY_WEEK = {1: _default_reading_content_for_week(1)}
DEFAULT_ORID_CONDITION = os.getenv("ORID_DEFAULT_CONDITION", "genai")


def parse_book_pack(content: str) -> Optional[dict[str, Any]]:
    try:
        obj = json.loads(content)
        if isinstance(obj, dict) and obj.get("schema") == "book_pack_v1":
            return obj
    except Exception:
        pass
    return None


def pick_prompt_from_bank(book_pack: Optional[dict[str, Any]], stage: str, idx: int) -> str:
    bank = None
    if book_pack:
        bank = (book_pack.get("orid_prompt_bank", {}) or {}).get(stage, None)
    if isinstance(bank, list) and bank:
        return bank[idx % len(bank)]
    return ai_prompt_by_stage(stage)


def heuristic_pass(stage: str, student_text: str) -> Tuple[bool, str]:
    t = (student_text or "").strip()
    if not t:
        return False, "沒有輸入內容"

    if stage == "O":
        if len(t) >= 6:
            return True, "OK"
        return False, "內容太短，請補充一點事件"

    if stage == "R":
        emo_kw = [
            "開心", "難過", "生氣", "害怕", "擔心", "緊張",
            "失望", "感動", "驚訝", "覺得", "感到", "心情",
            "同情", "不公平",
        ]
        if any(k in t for k in emo_kw):
            return True, "OK"
        return False, "請加上一個感受/情緒詞（例如：難過、失望、生氣…）"

    if stage == "I":
        kw = ["因為", "所以", "我覺得", "提醒", "學到", "道理", "重要", "意義", "價值", "代表", "象徵"]
        if any(k in t for k in kw) and len(t) >= 10:
            return True, "OK"
        return False, "請說出你覺得的道理/意義（可以用『我覺得…因為…』）"

    kw = ["我會", "下次", "先", "再", "行動", "例如", "打算", "計畫", "做到", "深呼吸", "先問"]
    if any(k in t for k in kw) and len(t) >= 10:
        return True, "OK"
    return False, "請說一個你下次會做的具體行動（用『下次我會…』）"


def _extract_keyword(student_text: str) -> str:
    t = (student_text or "").strip()
    if not t:
        return ""
    t2 = re.sub(r"\s+", "", t)
    return t2[:12]


async def llm_generate_reply(
    stage: str,
    history: list[dict],
    book_pack: Optional[dict[str, Any]],
    stage_turn: int,
    required_pass: int,
    fallback_question: str,
) -> str:
    book_context = build_book_context_block(book_pack)
    system_prompt = build_orid_chat_system_prompt(
        stage=stage,
        stage_turn=stage_turn,
        required_pass=required_pass,
        fallback_question=_sanitize_one_question(fallback_question),
        book_context=book_context,
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)

    return await _chat_completion(
        messages,
        max_completion_tokens=OPENAI_MAX_COMPLETION_TOKENS,
        temperature=OPENAI_TEMPERATURE,
    )


async def run_orid_checker(
    *,
    student_text: str,
    book_pack: Optional[dict[str, Any]],
    stage: str,
    msg_texts: list[str],
) -> dict[str, Any]:
    """
    Run ORID Checker to get:
    - unsafe_language signal (force boundary + do NOT advance)
    - off_topic signal (force pull-back + do NOT advance)
    - suggested_question (book-anchored + stage-appropriate)
    """
    if not CHECKER_OK:
        return {}

    sys, user_msg = build_orid_checker_prompts(
        student_text=student_text,
        book_pack=book_pack,
        stage=stage,
        message_history=msg_texts,
        max_history=6,
    )

    raw = await _chat_completion(
        [
            {"role": "system", "content": sys},
            {"role": "user", "content": user_msg},
        ],
        max_completion_tokens=min(220, OPENAI_MAX_COMPLETION_TOKENS),
        temperature=OPENAI_TEMPERATURE,
    )

    obj = clamp_checker_output(parse_orid_checker_json(raw))
    if ORID_CHECKER_DEBUG:
        print("[ORID_CHECKER]", obj)
    return obj or {}


# ----------------------------
# Writing assist (one-click draft)
# ----------------------------
class WritingAssistRequest(BaseModel):
    session_id: UUID
    week: int = Field(..., ge=1, le=6)
    stage: str = Field(..., pattern="^(O|R|I|D)$")
    draft: str = Field("d1", pattern="^(d1|d2)$")
    base_text: Optional[str] = None


class WritingAssistResponse(BaseModel):
    stage: str
    draft: str
    draft_text: str
    tips: list[str] = []


async def llm_generate_writing(
    stage: str,
    draft: str,
    book_pack: Optional[dict[str, Any]],
    chat_history: list[str],
    base_text: Optional[str],
) -> WritingAssistResponse:
    recent = [x for x in chat_history if (x or "").strip()][-6:]
    recent_hint = " / ".join([x.strip() for x in recent]) if recent else "(尚無對話內容)"

    if draft == "d1":
        sys, user_msg = build_writing_d1_prompts(
            stage=stage,
            book_pack=book_pack,
            chat_recent_hint=recent_hint,
        )
        text = await _chat_completion(
            [
                {"role": "system", "content": sys},
                {"role": "user", "content": user_msg},
            ],
            max_completion_tokens=OPENAI_MAX_COMPLETION_TOKENS,
            temperature=OPENAI_TEMPERATURE,
        )
        return WritingAssistResponse(stage=stage, draft=draft, draft_text=text, tips=[])

    base = (base_text or "").strip() or "（學生尚未提供 Draft1）"
    sys, user_msg = build_writing_d2_prompts(
        stage=stage,
        book_pack=book_pack,
        chat_recent_hint=recent_hint,
        base_text=base,
    )

    raw = await _chat_completion(
        [
            {"role": "system", "content": sys},
            {"role": "user", "content": user_msg},
        ],
        max_completion_tokens=OPENAI_MAX_COMPLETION_TOKENS,
        temperature=OPENAI_TEMPERATURE,
    )

    if ASSIST_TEXT_SPLIT in raw:
        text_part, tips_part = raw.split(ASSIST_TEXT_SPLIT, 1)
        draft_text = text_part.strip()
        tips_lines = [x.strip() for x in tips_part.strip().splitlines() if x.strip()]
        tips = [re.sub(r"^\s*\d+\)\s*", "", x) for x in tips_lines][:3]
        return WritingAssistResponse(stage=stage, draft=draft, draft_text=draft_text, tips=tips)

    return WritingAssistResponse(stage=stage, draft=draft, draft_text=raw, tips=[])


# ----------------------------
# Writing feedback (experiment vs control)
# ----------------------------
class WritingFeedbackRequest(BaseModel):
    session_id: UUID
    week: int = Field(..., ge=1, le=6)
    stage: str = Field(..., pattern="^(O|R|I|D)$")
    draft: str = Field("d1", pattern="^(d1|d2)$")
    text: Optional[str] = None
    save: bool = True


class WritingFeedbackResponse(BaseModel):
    stage: str
    draft: str
    ok: bool
    missing: list[str] = []
    suggestions: list[str] = []
    example: Optional[str] = None
    improved: Optional[str] = None
    meta: dict[str, Any] = {}


def _control_feedback(stage: str, text: str) -> Tuple[bool, list[str], list[str], Optional[str]]:
    t = (text or "").strip()
    missing: list[str] = []
    suggestions: list[str] = []

    def _has_sentence() -> bool:
        return "。" in t or "！" in t or "？" in t

    if len(t) < 12:
        missing.append("字數偏短")
        suggestions.append("至少寫 2 句、每句說清楚一件事")

    if stage == "O":
        if not _has_sentence():
            missing.append("缺少完整句子")
            suggestions.append("用『角色＋做了什麼』寫成句子（加上句號）")
        if len(t) < 25:
            missing.append("事件描述不夠")
            suggestions.append("補上『發生了什麼→後來怎樣』的順序")
        example = "故事裡，阿松爺爺很珍惜柿子樹，所以一直不想分給孩子們。後來奶奶提醒可以留下種子，大家一起處理播種，爺爺的想法慢慢改變。"

    elif stage == "R":
        emo_kw = ["開心", "難過", "生氣", "害怕", "擔心", "緊張", "失望", "感動", "驚訝", "不公平"]
        if not any(k in t for k in emo_kw):
            missing.append("缺少情緒/感受詞")
            suggestions.append("加上一個情緒詞（例如：難過、失望、生氣…）")
        if "因為" not in t:
            missing.append("缺少原因")
            suggestions.append("用『因為…所以我覺得…』把原因寫出來")
        example = "我覺得很失望，因為孩子們只能看著柿子卻吃不到，好像被排除在外。"

    elif stage == "I":
        if not any(k in t for k in ["我覺得", "提醒", "學到", "道理", "價值", "重要", "意義"]):
            missing.append("缺少道理/意義")
            suggestions.append("用『我覺得這個故事提醒我們…』寫出一個道理")
        if "因為" not in t and "所以" not in t:
            missing.append("缺少理由")
            suggestions.append("補一句理由（因為… / 所以…）")
        example = "我覺得故事提醒我們要學會分享，因為把好東西留給自己只會讓別人受傷，大家一起做反而更快樂。"

    else:  # D
        if "我會" not in t and "下次" not in t:
            missing.append("缺少具體行動句")
            suggestions.append("用『下次我會…』寫出你要做的行動")
        if len(t) < 25:
            missing.append("行動不夠具體")
            suggestions.append("補上『情境＋做法＋怎麼確認做到了』")
        example = "下次我想獨占時，我會先停三秒深呼吸，再問對方可不可以一起分享，最後看看大家是不是都能得到一點。"

    ok = len(missing) == 0
    return ok, missing[:3], suggestions[:3], example


class GenAIFeedbackOutput(BaseModel):
    ok: bool
    missing: list[str]
    suggestions: list[str]
    example: Optional[str]
    improved: Optional[str]

async def _genai_feedback(
    *,
    stage: str,
    text: str,
    book_pack: Optional[dict[str, Any]],
) -> Tuple[bool, list[str], list[str], Optional[str], Optional[str]]:
    sys, user_msg = build_genai_feedback_prompts(stage=stage, text=text, book_pack=book_pack)

    if client is None:
        return False, [], [], None, None

    kwargs = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": sys},
            {"role": "user", "content": user_msg},
        ],
        "response_format": GenAIFeedbackOutput,
    }
    if OPENAI_MAX_COMPLETION_TOKENS is not None:
        kwargs["max_completion_tokens"] = OPENAI_MAX_COMPLETION_TOKENS
    if OPENAI_TEMPERATURE is not None:
        kwargs["temperature"] = OPENAI_TEMPERATURE

    try:
        resp = await client.beta.chat.completions.parse(**kwargs)
    except BadRequestError as e:
        msg = str(e)
        if "temperature" in msg and ("unsupported" in msg or "Only the default" in msg):
            kwargs.pop("temperature", None)
            resp = await client.beta.chat.completions.parse(**kwargs)
        elif "max_completion_tokens" in msg and "unsupported" in msg:
            kwargs.pop("max_completion_tokens", None)
            resp = await client.beta.chat.completions.parse(**kwargs)
        else:
            raise

    parsed = resp.choices[0].message.parsed
    if not parsed:
        return False, [], [], None, None

    ok = bool(parsed.ok)
    missing = [str(x) for x in parsed.missing] if parsed.missing else []
    suggestions = [str(x) for x in parsed.suggestions] if parsed.suggestions else []
    example = str(parsed.example) if parsed.example else None
    improved = str(parsed.improved) if parsed.improved else None

    if (not missing) and (not suggestions):
        ok2, miss2, sug2, ex2 = _control_feedback(stage, text)
        ok = ok or ok2
        missing = missing or miss2
        suggestions = suggestions or sug2
        example = example or ex2

    return ok, missing[:3], suggestions[:3], example, improved


def _ensure_orid_writing_v1(week: int) -> dict[str, Any]:
    return {
        "schema": "orid_writing_v1",
        "week": week,
        "stages": {
            "O": {"d1": "", "d2": ""},
            "R": {"d1": "", "d2": ""},
            "I": {"d1": "", "d2": ""},
            "D": {"d1": "", "d2": ""},
        },
    }


# ----------------------------
# Routes
# ----------------------------
@router.post("/readings", response_model=ReadingRead)
async def create_reading(
    data: ReadingCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    reading = Reading(**data.model_dump())
    db.add(reading)
    await db.commit()
    await db.refresh(reading)
    return reading


@router.get("/readings/{reading_id}", response_model=ReadingRead)
async def get_reading(
    reading_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    r = await db.execute(select(Reading).filter(Reading.id == reading_id))
    reading = r.scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    return reading


@router.post("/sessions", response_model=OridSessionRead)
async def create_session(
    data: OridSessionCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    r = await db.execute(select(Reading).filter(Reading.id == data.reading_id))
    reading = r.scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")

    s = OridSession(
        user_id=user.id,
        reading_id=data.reading_id,
        condition=data.condition,
        current_stage="O",
        stage_turn=0,
        thread_id=None,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@router.post("/sessions/ensure", response_model=OridSessionRead)
async def ensure_session(
    week: int = Query(..., ge=1, le=6),
    force_new: bool = Query(False, description="true 時強制建立新 session；false 取最近一次。"),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    title = DEFAULT_READING_TITLE_TEMPLATE.format(week=week)

    if not force_new:
        s_stmt = (
            select(OridSession)
            .join(Reading, OridSession.reading_id == Reading.id)
            .where(OridSession.user_id == user.id, Reading.title == title)
            .order_by(OridSession.created_at.desc())
            .limit(1)
        )
        s_res = await db.execute(s_stmt)
        session = s_res.scalars().first()
        if session:
            return session

    r_stmt = (
        select(Reading)
        .where(Reading.title == title)
        .order_by(Reading.created_at.desc())
        .limit(1)
    )
    r_res = await db.execute(r_stmt)
    reading = r_res.scalars().first()

    if not reading:
        content = DEFAULT_READING_CONTENT_BY_WEEK.get(week, _default_reading_content_for_week(week))
        reading = Reading(title=title, content=content)
        db.add(reading)
        await db.commit()
        await db.refresh(reading)

    new_session = OridSession(
        user_id=user.id,
        reading_id=reading.id,
        condition=DEFAULT_ORID_CONDITION,
        current_stage="O",
        stage_turn=0,
        thread_id=None,
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session


async def generate_natural_pullback(student_text: str, fallback_q: str, custom_hint: Optional[str] = None) -> str:
    """Outsources empathy to LLM while strictly defining the fallback question."""
    if custom_hint:
        sys = f"你是一位溫暖的國小閱讀老師。學生回答不够完整（原因：{custom_hint}）。請用「短短一句話」自然地承接學生的話並給予鼓勵，然後在第二句話【一字不漏】接上這個問題：{fallback_q}。總計最多兩句話。"
    else:
        sys = f"你是一位溫暖幽默的國小閱讀老師。學生剛剛可能離題或閒聊了。請用「短短一句話」自然且帶點幽默地接住他講的話，然後在第二句話【一字不漏】接回這個正軌問題：{fallback_q}。總計最多兩句話。"
        
    raw = await _chat_completion(
        [
            {"role": "system", "content": sys},
            {"role": "user", "content": f"學生說：{student_text}"},
        ],
        max_completion_tokens=150,
        temperature=0.7,
    )
    return raw.strip() if raw.strip() else f"我們先回到故事。{fallback_q}"

@router.post("/chat", response_model=OridChatResponse)
async def chat(
    data: OridChatRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    r = await db.execute(select(OridSession).filter(OridSession.id == data.session_id))
    session = r.scalars().first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    student_text = (data.student_text or "").strip()
    if not student_text:
        raise HTTPException(status_code=400, detail="student_text is empty")

    rr = await db.execute(select(Reading).filter(Reading.id == session.reading_id))
    reading = rr.scalars().first()
    book_pack = parse_book_pack(reading.content) if (reading and reading.content) else None

    current_stage_before = (session.current_stage or "O").strip().upper()
    required_pass = ORID_REQUIRED_PASS_D if current_stage_before == "D" else ORID_REQUIRED_PASS_DEFAULT

    # 1) save student msg
    db.add(OridMessage(session_id=session.id, stage=current_stage_before, sender="student", text=student_text))
    await db.commit()

    # 2) load history
    q = await db.execute(
        select(OridMessage)
        .filter(OridMessage.session_id == session.id)
        .order_by(OridMessage.created_at.asc())
    )
    msgs = q.scalars().all()

    history: list[dict] = []
    for m in msgs[-ORID_HISTORY_LIMIT:]:
        role = "user" if m.sender == "student" else "assistant"
        history.append({"role": role, "content": m.text})

    # 3) run Safety Gate FIRST (Layer 1 & 2)
    is_unsafe, safety_reason = await check_safety(student_text)
    
    if is_unsafe:
        checker_unsafe = True
        checker_unsafe_reason = safety_reason
        checker_off_topic = False
        checker_reason = ""
        checker_q = ""
    else:
        # LLM Checker (Layer 3: Topic & Flow)
        msg_texts_for_checker = [m.text for m in msgs[-10:]]
        checker_obj: dict[str, Any] = {}
        try:
            checker_obj = await run_orid_checker(
                student_text=student_text,
                book_pack=book_pack,
                stage=current_stage_before,  # ✅ 重要：不跳階
                msg_texts=msg_texts_for_checker,
            )
        except Exception:
            checker_obj = {}

        checker_q = (checker_obj or {}).get("suggested_question") or ""
        checker_off_topic = bool((checker_obj or {}).get("off_topic", False))
        checker_reason = str((checker_obj or {}).get("reason", "") or "").strip()
        checker_unsafe = bool((checker_obj or {}).get("unsafe_language", False))
        checker_unsafe_reason = str((checker_obj or {}).get("unsafe_reason", "") or "").strip()

    # 4) fallback question selection (stage-anchored)
    ai_count_same_stage = len([m for m in msgs if m.sender == "ai" and m.stage == current_stage_before])

    if isinstance(checker_q, str) and checker_q.strip():
        fallback_q = _sanitize_one_question(checker_q.strip())
    else:
        fallback_q = _sanitize_one_question(pick_prompt_from_bank(book_pack, current_stage_before, ai_count_same_stage + 1))

    # ✅ Gate A: unsafe language -> NO PASS, NO ADVANCE, boundary + pull back
    if checker_unsafe:
        pass_ok = False
        reason = checker_unsafe_reason or "語氣不友善"
        final_ai_text = _two_sentence_ack_then_question(
            "我想跟你一起好好聊書，但我不接受傷人的話",
            fallback_q,
        )
        db.add(OridMessage(session_id=session.id, stage=current_stage_before, sender="ai", text=final_ai_text))
        await db.commit()
        await db.refresh(session)
        return OridChatResponse(
            session_id=session.id,
            stage=session.current_stage,
            ai_reply=final_ai_text,
            current_stage=session.current_stage,
            stage_turn=session.stage_turn,
            pass_ok=False,
            reason=reason,
            next_suggested=session.current_stage,
        )

    # ✅ Gate B: off-topic -> NO PASS, NO ADVANCE, gentle pull back
    if checker_off_topic and fallback_q:
        pass_ok = False
        reason = checker_reason or "先回到故事內容"
        final_ai_text = await generate_natural_pullback(student_text, fallback_q)
        db.add(OridMessage(session_id=session.id, stage=current_stage_before, sender="ai", text=final_ai_text))
        await db.commit()
        await db.refresh(session)
        return OridChatResponse(
            session_id=session.id,
            stage=session.current_stage,
            ai_reply=final_ai_text,
            current_stage=session.current_stage,
            stage_turn=session.stage_turn,
            pass_ok=False,
            reason=reason,
            next_suggested=session.current_stage,
        )

    # 5) normal LLM reply (only when safe + on-topic)
    raw_ai = await llm_generate_reply(
        stage=current_stage_before,
        history=history,
        book_pack=book_pack,
        stage_turn=session.stage_turn,
        required_pass=required_pass,
        fallback_question=fallback_q,
    )

    pass_ok, next_suggest, reason, clean_ai, has_tags = parse_control_tags(raw_ai)

    if not has_tags:
        hp, hr = heuristic_pass(current_stage_before, student_text)
        pass_ok = hp
        reason = None if hp else hr

    will_advance = False
    if pass_ok:
        session.stage_turn += 1

    if pass_ok and (session.stage_turn >= required_pass) and (session.current_stage != "D"):
        session.current_stage = next_stage(session.current_stage)
        session.stage_turn = 0
        will_advance = True

    final_ai_text = clean_ai.strip() if clean_ai else ""

    # ✅ 推進到下一階段：自然轉場 + 下一題（仍一個問號）
    if will_advance:
        new_stage = (session.current_stage or "O").strip().upper()
        ai_count_new_stage = len([m for m in msgs if m.sender == "ai" and m.stage == new_stage])
        q2_raw = pick_prompt_from_bank(book_pack, new_stage, ai_count_new_stage)
        q2 = _sanitize_one_question(q2_raw)
        prefix = (STAGE_TRANSITION_PREFIX.get(new_stage) or "").strip()
        final_ai_text = _two_sentence_ack_then_question(prefix or "好，我們繼續聊下去", q2)
    else:
        if not final_ai_text:
            if pass_ok:
                q2 = fallback_q or _sanitize_one_question(
                    pick_prompt_from_bank(book_pack, current_stage_before, ai_count_same_stage + 1)
                )
                final_ai_text = await generate_natural_pullback(student_text, q2)
            else:
                short_reason = (reason or "再補充一點就更完整了").strip()
                final_ai_text = await generate_natural_pullback(student_text, fallback_q, custom_hint=short_reason)

    ai_stage_for_save = session.current_stage if will_advance else current_stage_before
    db.add(OridMessage(session_id=session.id, stage=ai_stage_for_save, sender="ai", text=final_ai_text))

    await db.commit()
    await db.refresh(session)

    response_stage = session.current_stage
    return OridChatResponse(
        session_id=session.id,
        stage=response_stage,
        ai_reply=final_ai_text,
        current_stage=session.current_stage,
        stage_turn=session.stage_turn,
        pass_ok=pass_ok,
        reason=reason if (not pass_ok) else None,
        next_suggested=(next_suggest or response_stage),
    )


@router.post("/writings/assist", response_model=WritingAssistResponse)
async def writing_assist(
    data: WritingAssistRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    r = await db.execute(select(OridSession).filter(OridSession.id == data.session_id))
    session = r.scalars().first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    rr = await db.execute(select(Reading).filter(Reading.id == session.reading_id))
    reading = rr.scalars().first()
    book_pack = parse_book_pack(reading.content) if (reading and reading.content) else None

    q = await db.execute(
        select(OridMessage)
        .filter(OridMessage.session_id == session.id)
        .order_by(OridMessage.created_at.asc())
    )
    msgs = q.scalars().all()
    student_lines = [m.text for m in msgs if m.sender == "student"]

    return await llm_generate_writing(
        stage=data.stage,
        draft=data.draft,
        book_pack=book_pack,
        chat_history=student_lines,
        base_text=data.base_text,
    )


@router.post("/writings/feedback", response_model=WritingFeedbackResponse)
async def writing_feedback(
    data: WritingFeedbackRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    r = await db.execute(select(OridSession).filter(OridSession.id == data.session_id))
    session = r.scalars().first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    rr = await db.execute(select(Reading).filter(Reading.id == session.reading_id))
    reading = rr.scalars().first()
    book_pack = parse_book_pack(reading.content) if (reading and reading.content) else None

    text = (data.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")

    condition = (session.condition or DEFAULT_ORID_CONDITION).strip().lower()

    if condition == "control":
        ok, missing, suggestions, example = _control_feedback(data.stage, text)
        improved = None
    else:
        ok, missing, suggestions, example, improved = await _genai_feedback(
            stage=data.stage, text=text, book_pack=book_pack
        )

    saved_to: Optional[str] = None
    if data.save:
        w_stmt = (
            select(OridWriting)
            .where(
                OridWriting.user_id == user.id,
                OridWriting.session_id == session.id,
                OridWriting.week == data.week,
            )
            .order_by(OridWriting.created_at.desc())
            .limit(1)
        )
        w_res = await db.execute(w_stmt)
        w = w_res.scalars().first()

        if w and w.content:
            try:
                obj = json.loads(w.content)
                if not (isinstance(obj, dict) and obj.get("schema") == "orid_writing_v1"):
                    obj = _ensure_orid_writing_v1(data.week)
            except Exception:
                obj = _ensure_orid_writing_v1(data.week)
        else:
            obj = _ensure_orid_writing_v1(data.week)

        stages = obj.get("stages") if isinstance(obj, dict) else None
        if not isinstance(stages, dict):
            obj["stages"] = _ensure_orid_writing_v1(data.week)["stages"]
            stages = obj["stages"]

        stage_obj = stages.get(data.stage)
        if not isinstance(stage_obj, dict):
            stages[data.stage] = {"d1": "", "d2": ""}
            stage_obj = stages[data.stage]

        stage_obj.setdefault("feedback", {})
        if isinstance(stage_obj["feedback"], dict):
            stage_obj["feedback"][data.draft] = {
                "ok": ok,
                "missing": missing,
                "suggestions": suggestions,
                "example": example,
                "improved": improved,
            }

        if data.draft == "d1":
            stage_obj["d1"] = stage_obj.get("d1") or text
        elif data.draft == "d2":
            stage_obj["d2"] = stage_obj.get("d2") or text

        content_str = json.dumps(obj, ensure_ascii=False)

        if w:
            w.content = content_str
            await db.commit()
            await db.refresh(w)
            saved_to = str(w.id)
        else:
            new_w = OridWriting(
                user_id=user.id,
                reading_id=session.reading_id,
                session_id=session.id,
                week=data.week,
                content=content_str,
            )
            db.add(new_w)
            await db.commit()
            await db.refresh(new_w)
            saved_to = str(new_w.id)

    return WritingFeedbackResponse(
        stage=data.stage,
        draft=data.draft,
        ok=ok,
        missing=missing,
        suggestions=suggestions,
        example=example,
        improved=improved,
        meta={
            "condition": condition,
            "model": OPENAI_MODEL,
            "max_completion_tokens": OPENAI_MAX_COMPLETION_TOKENS,
            "saved_to_writing_id": saved_to,
            "prompts_ok": PROMPTS_OK,
            "prompts_import_error": PROMPTS_IMPORT_ERROR,
            "openai_enabled": OPENAI_ENABLED,
            "checker_ok": CHECKER_OK,
            "checker_import_error": CHECKER_IMPORT_ERROR,
        },
    )


@router.post("/writings", response_model=OridWritingRead)
async def create_writing(
    data: OridWritingCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    r = await db.execute(select(OridSession).filter(OridSession.id == data.session_id))
    session = r.scalars().first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    rr = await db.execute(select(Reading).filter(Reading.id == data.reading_id))
    reading = rr.scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")

    if session.reading_id != data.reading_id:
        raise HTTPException(status_code=400, detail="reading_id does not match session.reading_id")

    if data.week < 1 or data.week > 6:
        raise HTTPException(status_code=400, detail="week must be between 1 and 6")

    if not data.content.strip():
        raise HTTPException(status_code=400, detail="content is empty")

    w = OridWriting(
        user_id=user.id,
        reading_id=data.reading_id,
        session_id=data.session_id,
        week=data.week,
        content=data.content.strip(),
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return w


@router.get("/writings", response_model=list[OridWritingRead])
async def list_writings(
    session_id: Optional[UUID] = Query(default=None),
    reading_id: Optional[UUID] = Query(default=None),
    week: Optional[int] = Query(default=None),
    latest: bool = Query(default=False),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    q = select(OridWriting).filter(OridWriting.user_id == user.id)

    if session_id:
        q = q.filter(OridWriting.session_id == session_id)
    if reading_id:
        q = q.filter(OridWriting.reading_id == reading_id)
    if week:
        q = q.filter(OridWriting.week == week)

    q = q.order_by(OridWriting.created_at.desc())
    if latest:
        q = q.limit(1)

    r = await db.execute(q)
    return r.scalars().all()


@router.put("/writings/{writing_id}", response_model=OridWritingRead)
async def update_writing(
    writing_id: UUID,
    data: OridWritingUpdate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    r = await db.execute(
        select(OridWriting).filter(
            OridWriting.id == writing_id,
            OridWriting.user_id == user.id,
        )
    )
    w = r.scalars().first()
    if not w:
        raise HTTPException(status_code=404, detail="Writing not found")

    content = (data.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is empty")

    w.content = content
    await db.commit()
    await db.refresh(w)
    return w


@router.get("/messages", response_model=list[OridMessageRead])
async def list_messages(
    session_id: UUID = Query(...),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    r = await db.execute(select(OridSession).filter(OridSession.id == session_id))
    session = r.scalars().first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    q = select(OridMessage).filter(OridMessage.session_id == session_id)
    q = q.order_by(OridMessage.created_at.asc() if order == "asc" else OridMessage.created_at.desc())
    q = q.limit(limit)

    res = await db.execute(q)
    return res.scalars().all()

