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
# Prompt bank & Checker
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
from app.prompts.writing_hints import build_writing_hints_prompts
from app.prompts.orid_checker import (
    build_orid_checker_prompts,
    parse_orid_checker_json,
    clamp_checker_output,
    looks_story_related_to_book,
    looks_obviously_offtopic,
)
from app.services.safety import check_safety
from app.services.orid_condition import normalize_orid_condition, is_control_condition
from app.services.orid_stage import build_stage_history, decide_stage_progress
from app.services.orid_writing_store import ensure_orid_writing_obj, upsert_feedback_into_stage


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

ORID_REQUIRED_PASS_DEFAULT = int(os.getenv("ORID_REQUIRED_PASS", "2"))
ORID_REQUIRED_PASS_O = int(os.getenv("ORID_REQUIRED_PASS_O", str(ORID_REQUIRED_PASS_DEFAULT)))
ORID_REQUIRED_PASS_R = int(os.getenv("ORID_REQUIRED_PASS_R", str(ORID_REQUIRED_PASS_DEFAULT)))
ORID_REQUIRED_PASS_I = int(os.getenv("ORID_REQUIRED_PASS_I", str(ORID_REQUIRED_PASS_DEFAULT)))
ORID_REQUIRED_PASS_D = int(os.getenv("ORID_REQUIRED_PASS_D", str(ORID_REQUIRED_PASS_DEFAULT)))

ORID_MIN_AI_TURNS_DEFAULT = int(os.getenv("ORID_MIN_AI_TURNS", "2"))
ORID_MIN_AI_TURNS_O = int(os.getenv("ORID_MIN_AI_TURNS_O", str(ORID_MIN_AI_TURNS_DEFAULT)))
ORID_MIN_AI_TURNS_R = int(os.getenv("ORID_MIN_AI_TURNS_R", str(ORID_MIN_AI_TURNS_DEFAULT)))
ORID_MIN_AI_TURNS_I = int(os.getenv("ORID_MIN_AI_TURNS_I", str(ORID_MIN_AI_TURNS_DEFAULT)))
ORID_MIN_AI_TURNS_D = int(os.getenv("ORID_MIN_AI_TURNS_D", str(ORID_MIN_AI_TURNS_DEFAULT)))

ORID_FOLLOWUP_MAX_COMPLETION_TOKENS = int(os.getenv("ORID_FOLLOWUP_MAX_COMPLETION_TOKENS", "120"))
ORID_FOLLOWUP_TEMPERATURE = float(os.getenv("ORID_FOLLOWUP_TEMPERATURE", "0.7"))

ORID_CHECKER_DEBUG = _env_bool("ORID_CHECKER_DEBUG", False)
ORID_ALLOW_HEURISTIC_PASS = _env_bool("ORID_ALLOW_HEURISTIC_PASS", False)


def get_required_pass(stage: str) -> int:
    s = (stage or "O").strip().upper()
    if s == "O":
        return ORID_REQUIRED_PASS_O
    if s == "R":
        return ORID_REQUIRED_PASS_R
    if s == "I":
        return ORID_REQUIRED_PASS_I
    if s == "D":
        return ORID_REQUIRED_PASS_D
    return ORID_REQUIRED_PASS_DEFAULT


def get_min_ai_turns(stage: str) -> int:
    s = (stage or "O").strip().upper()
    if s == "O":
        return ORID_MIN_AI_TURNS_O
    if s == "R":
        return ORID_MIN_AI_TURNS_R
    if s == "I":
        return ORID_MIN_AI_TURNS_I
    if s == "D":
        return ORID_MIN_AI_TURNS_D
    return ORID_MIN_AI_TURNS_DEFAULT


# ----------------------------
# ORID stage helpers
# ----------------------------
STAGE_ORDER = ["O", "R", "I", "D"]

DEFAULT_HINTS_BY_STAGE: dict[str, list[str]] = {
    "O": [
        "回想剛剛聊到的角色和事件",
        "可以用先…後來…來整理",
        "先寫故事裡真的發生的事",
    ],
    "R": [
        "先想你最明顯的感受",
        "可以用我感到…因為…",
        "把感受和故事畫面連起來",
    ],
    "I": [
        "想想故事提醒了你什麼",
        "可以用我覺得…因為…",
        "把你的想法和故事連起來",
    ],
    "D": [
        "想想下次你會怎麼做",
        "可以用下次我會…開頭",
        "行動要寫得具體一點",
    ],
}

_GENERIC_QUESTION_PATTERNS = [
    r"故事發生了什麼",
    r"說說故事",
    r"有什麼感覺",
    r"提醒我們什麼",
    r"你會怎麼做",
]


def next_stage(stage: str) -> str:
    if stage not in STAGE_ORDER:
        return "O"
    idx = STAGE_ORDER.index(stage)
    return STAGE_ORDER[min(idx + 1, len(STAGE_ORDER) - 1)]


def _sanitize_one_question(text: str) -> str:
    t = (text or "").strip().replace("?", "？")
    if not t:
        return "你可以再說清楚一點嗎？"
    if "？" not in t:
        return t + "？"
    first = t.split("？", 1)[0].strip()
    return first + "？"


def _looks_generic_question(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    return any(re.search(p, s) for p in _GENERIC_QUESTION_PATTERNS)


_GENERIC_ANCHOR_PREFIXES = (
    "提醒", "我們", "不要", "如果", "下次", "我會", "先", "再", "因為", "所以", "可以", "覺得", "感覺", "想法", "做法",
)


_ACTION_KW = ["下次", "我會", "先", "再", "怎麼做", "做法", "行動", "問清楚", "深呼吸", "停一下", "分享", "決定"]
_INTERPRETIVE_KW = ["提醒", "道理", "學到", "我覺得", "我認為", "代表", "意思", "重要", "價值", "因為", "所以"]
_REFLECTIVE_KW = ["感覺", "感受", "難過", "失望", "開心", "生氣", "不公平", "擔心", "安心", "害怕", "同情"]


def _count_hits(text: str, keywords: list[str]) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    return sum(1 for k in keywords if k in t)


def _detect_cross_stage_answer(current_stage: str, student_text: str) -> Optional[dict[str, str]]:
    s = (current_stage or "O").strip().upper()
    t = (student_text or "").strip()
    if not t:
        return None

    action_hits = _count_hits(t, _ACTION_KW)
    interpretive_hits = _count_hits(t, _INTERPRETIVE_KW)
    reflective_hits = _count_hits(t, _REFLECTIVE_KW)

    if s == "I" and action_hits >= 1 and interpretive_hits == 0:
        return {
            "detected_stage": "D",
            "reason": "先把做法留到下一段",
            "fallback_question": _sanitize_one_question(
                _pick_variant(
                    [
                        "先不急著講做法，你覺得這件事最提醒我們什麼",
                        "你剛剛想到的是做法，先把它放著。那這件事最提醒我們什麼",
                        "做法我們下一段會用到，現在先想這件事想告訴我們什麼",
                    ],
                    f"cross:I:D:{t}",
                )
            ),
            "ack": _pick_variant(
                [
                    "你剛剛想到的是可以怎麼做，這個想法先留著。",
                    "你剛剛提到的是做法，這個等一下很用得上。",
                    "你已經想到下一步怎麼做了，先把這個點記住。",
                ],
                f"cross-ack:I:D:{t}",
            ),
        }

    if s == "R" and interpretive_hits >= 1 and reflective_hits == 0:
        return {
            "detected_stage": "I",
            "reason": "先把感受說清楚",
            "fallback_question": _sanitize_one_question(
                _pick_variant(
                    [
                        "在想到道理前面，你那一刻最明顯的感受是什麼",
                        "你已經想到想法了，先回到那一刻，你最明顯的感受是什麼",
                        "我們先不急著講道理，你在故事裡最強烈的感覺是什麼",
                    ],
                    f"cross:R:I:{t}",
                )
            ),
            "ack": _pick_variant(
                [
                    "你剛剛已經開始在想道理了，先把這個點放著。",
                    "你剛剛提到的是想法，先回到那一刻的感受看看。",
                ],
                f"cross-ack:R:I:{t}",
            ),
        }

    return None


def ai_prompt_by_stage(stage: str) -> str:
    s = (stage or "O").strip().upper()
    if s == "O":
        return _sanitize_one_question("接著是哪一件事讓情況開始改變")
    if s == "R":
        return _sanitize_one_question("故事裡哪一幕最讓你有這種感覺")
    if s == "I":
        return _sanitize_one_question("故事裡哪個地方最能支持你的想法")
    return _sanitize_one_question("下次遇到類似情況，你會先做哪一個小動作")


def _two_sentence_ack_then_question(ack: str, question: str) -> str:
    a = (ack or "").strip()
    if not a:
        a = "我有接到你剛剛說的。"
    if not a.endswith(("。", "！", "～")):
        a += "。"
    q = _sanitize_one_question(question)
    return f"{a}{q}"


def _default_hints_for_stage(stage: str) -> list[str]:
    s = (stage or "O").strip().upper()
    return DEFAULT_HINTS_BY_STAGE.get(s, DEFAULT_HINTS_BY_STAGE["O"])


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
                "如果你是孩子們，只能看著柿子卻吃不到，你比較像哪個感覺，為什麼？",
                "如果你是阿松爺爺，你覺得他最擔心什麼？",
                "故事裡哪一個瞬間讓你心裡卡一下？",
                "你最同情誰，你願意替他說一句安慰的話嗎？",
                "如果這件事發生在你班上，你覺得大家心情會變成什麼樣？",
            ],
            "I": [
                "你覺得故事最想提醒我們的一個道理是什麼？再用一句話說原因。",
                "你覺得『留種子』在故事裡像在說什麼？",
                "你覺得分享為什麼能讓事情變好？",
                "阿松爺爺會改變的關鍵是什麼？",
                "如果把故事變成一句班級座右銘，你會寫哪一句？",
            ],
            "D": [
                "下次你也很想獨占時，你願意先做哪一個小行動讓自己冷靜？",
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


def heuristic_pass(stage: str, student_text: str, book_pack: Optional[dict[str, Any]] = None) -> Tuple[bool, str]:
    t = (student_text or "").strip()
    if not t:
        return False, "沒有輸入內容"

    if looks_obviously_offtopic(t, book_pack):
        return False, "先回到故事裡"

    if stage == "O":
        if not looks_story_related_to_book(t, book_pack):
            return False, "先回到故事裡發生的事"
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
        return False, "請加上一個感受或情緒詞"

    if stage == "I":
        kw = ["因為", "所以", "我覺得", "提醒", "學到", "道理", "重要", "意義", "價值", "代表", "象徵"]
        if any(k in t for k in kw) and len(t) >= 10:
            return True, "OK"
        return False, "請再說出你的想法和理由"

    kw = ["我會", "下次", "先", "再", "行動", "例如", "打算", "計畫", "做到", "深呼吸", "先問"]
    if any(k in t for k in kw) and len(t) >= 10:
        return True, "OK"
    return False, "請說一個更具體的小行動"


def _extract_keyword(student_text: str) -> str:
    t = (student_text or "").strip()
    if not t:
        return ""
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"[「」『』\"\'，。！？：；、（）()\[\]{}]", " ", t)
    parts = [p.strip() for p in t.split() if p.strip()]
    for p in parts:
        if 2 <= len(p) <= 10:
            return p[:10]
    t2 = re.sub(r"\s+", "", t)
    return t2[:10]


def _pick_variant(options: list[str], seed: str) -> str:
    if not options:
        return ""
    base = seed or "orid"
    idx = sum(ord(ch) for ch in base) % len(options)
    return options[idx]


def _split_sentences(text: str) -> list[str]:
    t = (text or "").strip()
    if not t:
        return []
    parts = re.split(r"(?<=[。！？!~～])\s*", t)
    return [p.strip() for p in parts if p.strip()]


def _normalize_first_sentence(text: str) -> str:
    t = (text or "").strip()
    t = PASS_RE.sub("", t)
    t = NEXT_RE.sub("", t)
    t = REASON_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""

    first = ""
    for s in _split_sentences(t):
        if "？" not in s and "?" not in s:
            first = s
            break
    if not first:
        first = _split_sentences(t)[0] if _split_sentences(t) else ""

    first = first.replace("?", "？")
    first = first.split("？", 1)[0].strip()
    first = re.sub(
        r"^(你說得很好|很好喔|懂了|我知道了|我有聽到|這個觀察很有意思|這個觀察很關鍵|這個地方很重要|我們先回到故事|我們先把故事說清楚一點)[，、 ]*",
        "",
        first,
    )
    first = re.sub(r"(現在進入下一階段|這一題|本階段|ORID)", "", first).strip(" ，、")
    first = re.sub(r"^你先用.?1.?2.?句話", "", first).strip(" ，、")
    if not first:
        return ""
    if not first.endswith(("。", "！", "～")):
        first += "。"
    return first


def _extract_question_sentence(text: str) -> str:
    for s in _split_sentences(text):
        if "？" in s or "?" in s:
            return _sanitize_one_question(s)
    return ""


def _focus_ack(student_text: str, kind: str = "followup") -> str:
    kw = _extract_keyword(student_text)
    if kw:
        pool_map = {
            "pullback": [
                f"你剛剛提到{kw}，先把這個地方放回故事裡看看。",
                f"你有說到{kw}，我們順著這個點接回故事。",
                f"你剛剛抓到{kw}了，我們把它跟故事連起來。",
            ],
            "transition": [
                f"你剛剛提到{kw}，這個變化我有接到。",
                f"你有說到{kw}，接下來可以再往下想一步。",
                f"你剛剛抓到{kw}，這讓後面更清楚了。",
            ],
            "unsafe": [
                "我想跟你好好聊書，但先不要用傷人的話。",
                "我們可以把話說好一點，再把重點放回故事。",
                "先把語氣放輕一點，我們再繼續聊故事。",
            ],
            "followup": [
                f"你剛剛提到{kw}，我想順著這裡再往下看。",
                f"你有說到{kw}，後面那一步也很值得看。",
                f"你剛剛抓到{kw}，我們就從這裡再多想一點。",
            ],
        }
        return _pick_variant(pool_map.get(kind, pool_map["followup"]), f"{kind}:{kw}")

    if kind == "pullback":
        return _pick_variant(
            [
                "你剛剛有提到一個點，我們把它接回故事裡看看。",
                "先接住你剛剛說的，我們再把它放回故事。",
            ],
            f"{kind}:{student_text}",
        )
    if kind == "transition":
        return _pick_variant(
            [
                "你剛剛有抓到一個重點，後面可以再往下想一步。",
                "你剛剛說的內容有接到故事後面的變化。",
            ],
            f"{kind}:{student_text}",
        )
    if kind == "unsafe":
        return _pick_variant(
            [
                "我想跟你好好聊書，但先不要用傷人的話。",
                "我們可以把話說好一點，再繼續聊故事。",
            ],
            f"{kind}:{student_text}",
        )
    return _pick_variant(
        [
            "你剛剛有接到故事裡的一個重點。",
            "你剛剛說的內容有碰到故事的關鍵地方。",
        ],
        f"{kind}:{student_text}",
    )


def _neutral_pullback_ack(seed: str = "") -> str:
    return _pick_variant(
        [
            "我們先把重點放回故事裡看看。",
            "先回到故事裡剛剛發生的事。",
            "我們把剛剛的話接回故事內容。",
        ],
        f"neutral-pullback:{seed}",
    )


def _cross_stage_ack(current_stage: str, student_text: str) -> Optional[str]:
    obj = _detect_cross_stage_answer(current_stage, student_text)
    if not obj:
        return None
    return str(obj.get("ack") or "").strip() or None


def _should_avoid_student_anchor_for_pullback(student_text: str, anchor_student_text: bool) -> bool:
    if not anchor_student_text:
        return True
    return looks_obviously_offtopic(student_text, None)


def _choose_question_from_candidates(*candidates: str) -> str:
    for c in candidates:
        if not c:
            continue
        q = _sanitize_one_question(c)
        if q:
            return q
    return "你可以再說清楚一點嗎？"


def _compose_reply_from_model(
    *,
    clean_ai: str,
    student_text: str,
    fallback_q: str,
    fallback_kind: str = "followup",
) -> str:
    ack = _normalize_first_sentence(clean_ai)
    if not ack:
        ack = _focus_ack(student_text, fallback_kind)

    model_q = _extract_question_sentence(clean_ai)
    if _looks_generic_question(model_q):
        model_q = ""

    q = _choose_question_from_candidates(model_q, fallback_q)
    return _two_sentence_ack_then_question(ack, q)


def _stage_recent_lines(msgs: list[OridMessage], stage: str, limit: int = 8) -> list[str]:
    out: list[str] = []
    for m in msgs:
        if (m.stage or "").strip().upper() != stage:
            continue
        prefix = "學生" if m.sender == "student" else "老師"
        out.append(f"{prefix}：{m.text}")
    return out[-limit:]


async def _generate_first_sentence(
    *,
    student_text: str,
    system_prompt: str,
    fallback_first: str,
) -> str:
    if client is None:
        return fallback_first

    try:
        raw = await _chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"學生剛剛說：{student_text}"},
            ],
            max_completion_tokens=ORID_FOLLOWUP_MAX_COMPLETION_TOKENS,
            temperature=ORID_FOLLOWUP_TEMPERATURE,
        )
        first = _normalize_first_sentence(raw)
        if first:
            return first
    except Exception:
        pass

    return fallback_first


async def llm_generate_reply(
    stage: str,
    history: list[dict],
    book_pack: Optional[dict[str, Any]],
    stage_turn: int,
    required_pass: int,
    ai_turn_count_same_stage: int,
    min_ai_turns_same_stage: int,
    fallback_question: str,
) -> str:
    book_context = build_book_context_block(book_pack)
    system_prompt = build_orid_chat_system_prompt(
        stage=stage,
        stage_turn=stage_turn,
        required_pass=required_pass,
        ai_turn_count_same_stage=ai_turn_count_same_stage,
        min_ai_turns_same_stage=min_ai_turns_same_stage,
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

    obj = clamp_checker_output(
        parse_orid_checker_json(raw),
        stage=stage,
        student_text=student_text,
    )
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
        return WritingAssistResponse(stage=stage, draft=draft, draft_text=text.strip(), tips=[])

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

    return WritingAssistResponse(stage=stage, draft=draft, draft_text=raw.strip(), tips=[])


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
            suggestions.append("用角色加事件寫成完整句子")
        if len(t) < 25:
            missing.append("事件描述不夠")
            suggestions.append("補上先發生什麼、後來怎樣")
        example = "故事裡，阿松爺爺很珍惜柿子樹，所以一開始不想把柿子分給孩子們。後來奶奶提醒可以留下種子，大家一起處理和播種，爺爺的想法也慢慢改變。"

    elif stage == "R":
        emo_kw = ["開心", "難過", "生氣", "害怕", "擔心", "緊張", "失望", "感動", "驚訝", "不公平"]
        if not any(k in t for k in emo_kw):
            missing.append("缺少感受詞")
            suggestions.append("加上一個明確的感受詞")
        if "因為" not in t:
            missing.append("缺少原因")
            suggestions.append("用因為把感受連回故事")
        example = "我覺得很失望，因為孩子們只能看著柿子卻吃不到，好像被排除在外。看到後來大家一起處理種子時，我又覺得比較安心。"

    elif stage == "I":
        if not any(k in t for k in ["我覺得", "提醒", "學到", "道理", "價值", "重要", "意義"]):
            missing.append("缺少道理")
            suggestions.append("寫出你學到或提醒到的事")
        if "因為" not in t and "所以" not in t:
            missing.append("缺少理由")
            suggestions.append("補一句故事裡的理由")
        example = "我覺得這個故事提醒我們要學會分享，因為只想把好東西留給自己，最後不會真的更快樂。當大家一起處理種子時，事情反而變得更好。"

    else:
        if "我會" not in t and "下次" not in t:
            missing.append("缺少行動句")
            suggestions.append("用下次我會開頭寫行動")
        if len(t) < 25:
            missing.append("行動不夠具體")
            suggestions.append("補上第一步和怎麼做到")
        example = "下次我也很想獨占時，我會先停一下深呼吸，再想想可不可以和別人一起分享。如果我誤會別人，我會先問清楚，不會急著生氣。"

    ok = len(missing) == 0
    return ok, missing[:3], suggestions[:3], example


class GenAIFeedbackOutput(BaseModel):
    ok: bool
    missing: list[str]
    suggestions: list[str]
    example: Optional[str]
    improved: Optional[str]


def _normalize_feedback_list(value: Any) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for x in value:
            s = str(x).strip()
            if s:
                out.append(s)
        return out[:3]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _extract_json_object(raw: str) -> dict[str, Any]:
    txt = (raw or "").strip()
    if not txt:
        return {}

    try:
        obj = json.loads(txt)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", txt)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    return {}


def _feedback_from_obj(
    *,
    stage: str,
    text: str,
    obj: dict[str, Any],
) -> Tuple[bool, list[str], list[str], Optional[str], Optional[str]]:
    ok = bool(obj.get("ok", False))
    missing = _normalize_feedback_list(obj.get("missing"))
    suggestions = _normalize_feedback_list(obj.get("suggestions"))

    example_raw = obj.get("example")
    improved_raw = obj.get("improved")

    example = str(example_raw).strip() if example_raw else None
    improved = str(improved_raw).strip() if improved_raw else None

    if (not missing) and (not suggestions):
        ok2, miss2, sug2, ex2 = _control_feedback(stage, text)
        ok = ok or ok2
        missing = missing or miss2
        suggestions = suggestions or sug2
        example = example or ex2

    if not improved:
        improved = example or text

    return ok, missing[:3], suggestions[:3], example, improved


async def _genai_feedback(
    *,
    stage: str,
    text: str,
    book_pack: Optional[dict[str, Any]],
) -> Tuple[bool, list[str], list[str], Optional[str], Optional[str]]:
    sys, user_msg = build_genai_feedback_prompts(stage=stage, text=text, book_pack=book_pack)

    if client is None:
        ok2, miss2, sug2, ex2 = _control_feedback(stage, text)
        return ok2, miss2, sug2, ex2, ex2

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
            elif "response_format" in msg and "unsupported" in msg:
                kwargs.pop("response_format", None)
                raise
            else:
                raise

        parsed = resp.choices[0].message.parsed
        if parsed:
            if hasattr(parsed, "model_dump"):
                obj = parsed.model_dump()
            elif isinstance(parsed, dict):
                obj = parsed
            else:
                obj = getattr(parsed, "__dict__", {}) or {}
            return _feedback_from_obj(stage=stage, text=text, obj=obj)

    except Exception as e:
        print("[writing_feedback][structured_parse_failed]", repr(e))

    try:
        raw = await _chat_completion(
            [
                {"role": "system", "content": sys},
                {"role": "user", "content": user_msg},
            ],
            max_completion_tokens=OPENAI_MAX_COMPLETION_TOKENS,
            temperature=OPENAI_TEMPERATURE,
        )
        obj = _extract_json_object(raw)
        if obj:
            return _feedback_from_obj(stage=stage, text=text, obj=obj)
    except Exception as e:
        print("[writing_feedback][manual_json_failed]", repr(e))

    ok2, miss2, sug2, ex2 = _control_feedback(stage, text)
    return ok2, miss2, sug2, ex2, ex2


class GenerateHintsRequest(BaseModel):
    session_id: UUID
    stage: str = Field(..., pattern="^(O|R|I|D)$")


class GenerateHintsResponse(BaseModel):
    hints: list[str]


def _extract_hint_lines(raw: str) -> list[str]:
    hints: list[str] = []
    for line in (raw or "").split("\n"):
        line = line.strip()
        line = re.sub(r"^[\-\*\d\.\)\s]+", "", line)
        if line:
            hints.append(line)
    return hints[:3]


async def generate_natural_pullback(
    student_text: str,
    fallback_q: str,
    custom_hint: Optional[str] = None,
    *,
    anchor_student_text: bool = True,
    current_stage: Optional[str] = None,
) -> str:
    avoid_student_anchor = _should_avoid_student_anchor_for_pullback(student_text, anchor_student_text)
    fallback_first = (
        _neutral_pullback_ack(student_text)
        if avoid_student_anchor
        else _focus_ack(student_text, "pullback")
    )
    hint_line = f"學生目前還缺：{custom_hint}" if custom_hint else "學生剛剛可能偏題或內容還不夠完整。"

    anchor_rule = (
        "這一句不要直接引用學生剛剛那句離題內容，也不要重複生活瑣事；要用中性方式把重點拉回故事。"
        if avoid_student_anchor
        else "這一句要自然承接學生剛剛說的內容。"
    )

    user_for_first = "學生剛剛離題了，請用中性方式把話題拉回故事。" if avoid_student_anchor else student_text

    sys = f"""
你是一位溫暖、自然的國小閱讀老師。
{hint_line}

請只輸出第一句，不要輸出第二句，不要列點：
- {anchor_rule}
- 不要責備
- 不要做心理推測
- 不要用模板稱讚
- 不要提到階段、任務、系統
- 12 到 28 個字左右
""".strip()

    first = await _generate_first_sentence(
        student_text=user_for_first,
        system_prompt=sys,
        fallback_first=fallback_first,
    )
    return _two_sentence_ack_then_question(first, fallback_q)


async def generate_stage_transition_reply(
    *,
    student_text: str,
    from_stage: str,
    to_stage: str,
    next_q: str,
) -> str:
    fallback_first = _focus_ack(student_text, "transition")

    sys = f"""
你是一位自然、親切的國小閱讀老師。
學生剛剛的回答已經足夠，現在準備從 {from_stage} 自然接到 {to_stage}。

請只輸出第一句，不要輸出第二句，不要列點：
- 這一句要自然回應學生剛剛說的內容，讓他感覺有被接住
- 不要寫成系統轉場
- 不要說現在進入下一階段
- 不要說 O / R / I / D
- 不要用模板稱讚
- 不要做心理推測
- 12 到 28 個字左右
""".strip()

    first = await _generate_first_sentence(
        student_text=student_text,
        system_prompt=sys,
        fallback_first=fallback_first,
    )
    return _two_sentence_ack_then_question(first, next_q)


@router.post("/writings/generate_hints", response_model=GenerateHintsResponse)
async def generate_hints(
    data: GenerateHintsRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    r = await db.execute(select(OridSession).filter(OridSession.id == data.session_id))
    session = r.scalars().first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    q = await db.execute(
        select(OridMessage)
        .filter(OridMessage.session_id == session.id)
        .filter(OridMessage.stage == data.stage)
        .order_by(OridMessage.created_at.asc())
    )
    msgs = q.scalars().all()

    chat_history = _stage_recent_lines(msgs, data.stage, limit=10)

    if client is None or len(chat_history) == 0:
        return GenerateHintsResponse(hints=_default_hints_for_stage(data.stage))

    try:
        sys_prompt, user_msg = build_writing_hints_prompts(stage=data.stage, chat_history=chat_history)

        raw = await _chat_completion(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_completion_tokens=150,
            temperature=0.7,
        )

        hints = _extract_hint_lines(raw)
        if not hints:
            hints = _default_hints_for_stage(data.stage)

        return GenerateHintsResponse(hints=hints[:3])

    except Exception as e:
        print("[generate_hints][fallback]", repr(e))
        return GenerateHintsResponse(hints=_default_hints_for_stage(data.stage))


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
        condition=normalize_orid_condition(data.condition, default=DEFAULT_ORID_CONDITION),
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
    condition: Optional[str] = Query(default=None),
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

    new_condition = normalize_orid_condition(condition, default=DEFAULT_ORID_CONDITION)

    new_session = OridSession(
        user_id=user.id,
        reading_id=reading.id,
        condition=new_condition,
        current_stage="O",
        stage_turn=0,
        thread_id=None,
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session


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
    required_pass = get_required_pass(current_stage_before)

    db.add(OridMessage(session_id=session.id, stage=current_stage_before, sender="student", text=student_text))
    await db.commit()

    q = await db.execute(
        select(OridMessage)
        .filter(OridMessage.session_id == session.id)
        .order_by(OridMessage.created_at.asc())
    )
    msgs = q.scalars().all()

    history = build_stage_history(
        msgs,
        current_stage=current_stage_before,
        history_limit=ORID_HISTORY_LIMIT,
    )

    is_unsafe, safety_reason = await check_safety(student_text)

    if is_unsafe:
        checker_unsafe = True
        checker_unsafe_reason = safety_reason
        checker_off_topic = False
        checker_reason = ""
        checker_q = ""
    else:
        msg_texts_for_checker = [m.text for m in msgs[-10:]]
        checker_obj: dict[str, Any] = {}
        try:
            checker_obj = await run_orid_checker(
                student_text=student_text,
                book_pack=book_pack,
                stage=current_stage_before,
                msg_texts=msg_texts_for_checker,
            )
        except Exception:
            checker_obj = {}

        checker_q = (checker_obj or {}).get("suggested_question") or ""
        checker_off_topic = bool((checker_obj or {}).get("off_topic", False))
        checker_reason = str((checker_obj or {}).get("reason", "") or "").strip()
        checker_unsafe = bool((checker_obj or {}).get("unsafe_language", False))
        checker_unsafe_reason = str((checker_obj or {}).get("unsafe_reason", "") or "").strip()

    story_related = looks_story_related_to_book(student_text, book_pack)
    obvious_offtopic = looks_obviously_offtopic(student_text, book_pack)
    cross_stage_obj = _detect_cross_stage_answer(current_stage_before, student_text)
    if (not checker_unsafe) and obvious_offtopic:
        checker_off_topic = True
        if not checker_reason or checker_reason == "OK":
            checker_reason = "先回到故事"
        if _looks_generic_question(checker_q):
            checker_q = ""

    ai_count_same_stage = len([m for m in msgs if m.sender == "ai" and m.stage == current_stage_before])
    prompt_q = pick_prompt_from_bank(book_pack, current_stage_before, ai_count_same_stage + 1)
    if cross_stage_obj and str(cross_stage_obj.get("fallback_question") or "").strip():
        fallback_q = _sanitize_one_question(str(cross_stage_obj.get("fallback_question")))
    else:
        fallback_q = _sanitize_one_question(checker_q.strip()) if isinstance(checker_q, str) and checker_q.strip() else _sanitize_one_question(prompt_q)

    if checker_unsafe:
        pass_ok = False
        reason = checker_unsafe_reason or "語氣不友善"
        final_ai_text = _two_sentence_ack_then_question(
            _focus_ack(student_text, "unsafe"),
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

    if checker_off_topic:
        pass_ok = False
        reason = checker_reason or "先回到故事"
        final_ai_text = await generate_natural_pullback(
            student_text,
            fallback_q,
            anchor_student_text=not obvious_offtopic,
            current_stage=current_stage_before,
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

    min_ai_turns_same_stage = get_min_ai_turns(current_stage_before)
    raw_ai = await llm_generate_reply(
        stage=current_stage_before,
        history=history,
        book_pack=book_pack,
        stage_turn=session.stage_turn,
        required_pass=required_pass,
        ai_turn_count_same_stage=ai_count_same_stage,
        min_ai_turns_same_stage=min_ai_turns_same_stage,
        fallback_question=fallback_q,
    )

    pass_ok, next_suggest, reason, clean_ai, has_tags = parse_control_tags(raw_ai)

    if not has_tags:
        hp, hr = heuristic_pass(current_stage_before, student_text, book_pack=book_pack)
        if ORID_ALLOW_HEURISTIC_PASS:
            pass_ok = hp
            reason = None if hp else hr
        else:
            pass_ok = False
            reason = hr if not hp else "請再補一點完整線索，我們再往下一段"

    if cross_stage_obj:
        pass_ok = False
        reason = str(cross_stage_obj.get("reason") or "先把這一段說清楚")

    if obvious_offtopic:
        pass_ok = False
        if not reason or reason == "OK":
            reason = "先回到故事"
    elif current_stage_before == "O" and pass_ok and not story_related:
        pass_ok = False
        reason = "先回到故事裡發生的事"

    decision = decide_stage_progress(
        current_stage=session.current_stage,
        stage_turn=session.stage_turn,
        required_pass=required_pass,
        pass_ok=pass_ok,
        ai_count_same_stage=ai_count_same_stage,
        min_ai_turns_same_stage=min_ai_turns_same_stage,
        next_stage_func=next_stage,
    )
    session.current_stage = decision.next_stage
    session.stage_turn = decision.next_stage_turn
    will_advance = decision.will_advance

    if will_advance:
        new_stage = (session.current_stage or "O").strip().upper()
        ai_count_new_stage = len([m for m in msgs if m.sender == "ai" and m.stage == new_stage])
        q2_raw = pick_prompt_from_bank(book_pack, new_stage, ai_count_new_stage)
        q2 = _sanitize_one_question(q2_raw)
        final_ai_text = await generate_stage_transition_reply(
            student_text=student_text,
            from_stage=current_stage_before,
            to_stage=new_stage,
            next_q=q2,
        )
    else:
        if pass_ok:
            q2 = _extract_question_sentence(clean_ai)
            if _looks_generic_question(q2):
                q2 = ""
            if not q2:
                q2 = fallback_q or _sanitize_one_question(
                    pick_prompt_from_bank(book_pack, current_stage_before, ai_count_same_stage + 1)
                )
            final_ai_text = _compose_reply_from_model(
                clean_ai=clean_ai,
                student_text=student_text,
                fallback_q=q2,
                fallback_kind="followup",
            )
        else:
            short_reason = (reason or "再補充一點就更完整了").strip()
            final_ai_text = await generate_natural_pullback(
                student_text,
                fallback_q,
                custom_hint=short_reason,
                anchor_student_text=not obvious_offtopic,
                current_stage=current_stage_before,
            )

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

    stage_history = _stage_recent_lines(msgs, data.stage, limit=8)

    return await llm_generate_writing(
        stage=data.stage,
        draft=data.draft,
        book_pack=book_pack,
        chat_history=stage_history,
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

    condition = normalize_orid_condition(session.condition, default=DEFAULT_ORID_CONDITION)

    if is_control_condition(condition, default=DEFAULT_ORID_CONDITION):
        ok, missing, suggestions, example = _control_feedback(data.stage, text)
        example = None
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

        obj = ensure_orid_writing_obj(
            raw_content=(w.content if w else None),
            week=data.week,
            empty_factory=_ensure_orid_writing_v1,
        )
        obj = upsert_feedback_into_stage(
            obj=obj,
            stage=data.stage,
            draft=data.draft,
            text=text,
            ok=ok,
            missing=missing,
            suggestions=suggestions,
            example=example,
            improved=improved,
            empty_factory=_ensure_orid_writing_v1,
        )

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
