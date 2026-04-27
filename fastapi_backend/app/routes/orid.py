from __future__ import annotations

from uuid import UUID
from typing import Optional, Any, Tuple, List, Dict
import os
import re
import json
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
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
    OridWritingCreate, OridWritingUpdate, OridWritingRead,
    OridMessageRead,
    WritingCoachChatRequest,
    WritingCoachChatResponse,
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
from app.prompts.writing_feedback import build_genai_feedback_prompts
from app.prompts.writing_assist import (
    ASSIST_TEXT_SPLIT,
    build_writing_d1_prompts,
    build_writing_d2_prompts,
)
from app.prompts.writing_coach_chat import (
    build_feedback_narration_prompt,
    build_writing_coach_system_prompt,
    format_control_feedback_reply,
    format_control_free_text_reply,
)
from app.prompts.orid_checker import (
    build_book_grounding_checker_prompts,
    looks_story_related_to_book,
    looks_obviously_offtopic,
    looks_likely_factual_mismatch,
    looks_likely_ungrounded_in_book,
    parse_book_grounding_checker_json,
)
from app.services.safety import check_safety
from app.services.orid_condition import normalize_orid_condition, is_control_condition
from app.services.orid_stage import build_stage_history, decide_stage_progress, resolve_stage_thresholds
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

ORID_MIN_AI_TURNS_DEFAULT = int(os.getenv("ORID_MIN_AI_TURNS", "1"))
ORID_MIN_AI_TURNS_O = int(os.getenv("ORID_MIN_AI_TURNS_O", str(ORID_MIN_AI_TURNS_DEFAULT)))
ORID_MIN_AI_TURNS_R = int(os.getenv("ORID_MIN_AI_TURNS_R", str(ORID_MIN_AI_TURNS_DEFAULT)))
ORID_MIN_AI_TURNS_I = int(os.getenv("ORID_MIN_AI_TURNS_I", str(ORID_MIN_AI_TURNS_DEFAULT)))
ORID_MIN_AI_TURNS_D = int(os.getenv("ORID_MIN_AI_TURNS_D", str(ORID_MIN_AI_TURNS_DEFAULT)))
ORID_PROGRESSION_MODE = (os.getenv("ORID_PROGRESSION_MODE") or "guided").strip().lower()
ORID_GUIDED_STUCK_THRESHOLD = int(os.getenv("ORID_GUIDED_STUCK_THRESHOLD", "3"))
ORID_GUIDED_PASS_RELAX = int(os.getenv("ORID_GUIDED_PASS_RELAX", "1"))
ORID_GUIDED_MIN_PASS = int(os.getenv("ORID_GUIDED_MIN_PASS", "1"))
ORID_GUIDED_RELAX_MIN_TURNS = int(os.getenv("ORID_GUIDED_RELAX_MIN_TURNS", "0"))

ORID_FOLLOWUP_MAX_COMPLETION_TOKENS = int(os.getenv("ORID_FOLLOWUP_MAX_COMPLETION_TOKENS", "120"))
ORID_FOLLOWUP_TEMPERATURE = float(os.getenv("ORID_FOLLOWUP_TEMPERATURE", "0.7"))
ORID_FEEDBACK_MAX_COMPLETION_TOKENS = int(
    os.getenv(
        "ORID_FEEDBACK_MAX_COMPLETION_TOKENS",
        str(max(int(OPENAI_MAX_COMPLETION_TOKENS or 0), 1800)),
    )
)
ORID_FEEDBACK_RETRY_MAX_COMPLETION_TOKENS = int(
    os.getenv(
        "ORID_FEEDBACK_RETRY_MAX_COMPLETION_TOKENS",
        str(max(ORID_FEEDBACK_MAX_COMPLETION_TOKENS, 3000)),
    )
)
ORID_OFFTOPIC_STRICT = _env_bool("ORID_OFFTOPIC_STRICT", False)
ORID_CHAT_PROMPT_VERSION = os.getenv("ORID_CHAT_PROMPT_VERSION", "orid-chat-v2.2")
ORID_LIMIT_PER_MINUTE = int(os.getenv("ORID_LIMIT_PER_MINUTE", "30"))
ORID_LIMIT_WINDOW_SECONDS = int(os.getenv("ORID_LIMIT_WINDOW_SECONDS", "60"))
ORID_MAIN_FALLBACK_TEMPERATURE = float(os.getenv("ORID_MAIN_FALLBACK_TEMPERATURE", "0.9"))

ORID_ALLOW_HEURISTIC_PASS = _env_bool("ORID_ALLOW_HEURISTIC_PASS", False)
ORID_ENABLE_RATE_LIMIT = _env_bool("ORID_ENABLE_RATE_LIMIT", True)

_CHAT_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def _draft_label_zh(draft: str) -> str:
    return "草稿1" if (draft or "").strip().lower() == "d1" else "草稿2"
_STUCK_ROUNDS_BY_SESSION_STAGE: dict[str, int] = {}


def _stuck_key(session_id: UUID, stage: str) -> str:
    return f"{session_id}:{(stage or 'O').strip().upper()}"


def _get_stuck_rounds(session_id: UUID, stage: str) -> int:
    return max(0, int(_STUCK_ROUNDS_BY_SESSION_STAGE.get(_stuck_key(session_id, stage), 0)))


def _set_stuck_rounds(session_id: UUID, stage: str, value: int) -> None:
    key = _stuck_key(session_id, stage)
    v = max(0, int(value))
    if v == 0:
        _STUCK_ROUNDS_BY_SESSION_STAGE.pop(key, None)
    else:
        _STUCK_ROUNDS_BY_SESSION_STAGE[key] = v


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

_GENERIC_QUESTION_PATTERNS = [
    r"故事發生了什麼",
    r"說說故事",
    r"有什麼感覺",
    r"提醒我們什麼",
    r"你會怎麼做",
    r"接著是哪一件事讓情況開始改變",
    r"接著發生了什麼",
    r"哪一件事讓情況開始改變",
    r"讓情況開始改變",
    r"情況開始改變",
    r"哪一件事讓",
]

_O_ANGLE_FALLBACKS: list[str] = [
    "照時間順序，你剛剛說的那段之後，故事裡接著發生了什麼",
    "接下來是誰先做了什麼，讓後面跟著變化",
    "如果把那一幕再放大一點，你還看到故事裡哪個關鍵動作",
    "你覺得先出現的是誤會還是情緒，故事裡哪裡看得出來",
    "故事裡下一個轉折點發生在什麼場景",
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
    # Trim obvious stutter artifacts in generated question text.
    t = re.sub(r"\s+", " ", t)
    for m in re.finditer(r"([\u4e00-\u9fff])\1{1,}", t):
        ch = m.group(1)
        if ch not in {"哈", "呵", "啊", "嗯"}:
            t = t.replace(m.group(0), ch)
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
        "version": 3,
        "rag_source": "file",
        "embedding_bundle_id": "week_1",
        "full_text_path": "/app/shared-data/book_pack_week1.json",
        "book_title": "阿松爺爺的柿子樹",
        "grade": "國小高年級（五、六年級）",
        "core_theme": ["分享與獨占", "轉念與創意", "衝動的後果", "把好東西變成大家的好"],
        "characters": [
            {"name": "阿松爺爺", "role": "很喜歡自家甜柿子，一開始常獨占，不想分給別人"},
            {"name": "哎唷奶奶", "role": "新鄰居，總能把柿子蒂、葉子、樹枝變成有趣又有用的東西"},
            {"name": "小朋友們", "role": "跟著哎唷奶奶一起玩、一起做，也願意最後一起幫忙播種"},
        ],
        "setting": ["阿松爺爺家與隔壁哎唷奶奶家", "柿子樹旁與院子", "秋天柿子成熟時"],
        "key_events": [
            "阿松爺爺家的柿子很甜，但他一直獨占，故意在大家面前大口吃。",
            "哎唷奶奶搬來後，阿松爺爺只給她柿子蒂；她卻開心收下。",
            "哎唷奶奶和孩子們用柿子蒂玩陀螺，阿松爺爺怕被要走，急忙把柿子全藏進倉庫。",
            "後來他又把葉子打落藏起來、再把樹枝拿給大家；哎唷奶奶和孩子們照樣玩得很開心。",
            "阿松爺爺一急之下砍樹，回神只剩樹樁，難過地哭了。",
            "哎唷奶奶提醒：若留一顆柿子，裡面的子可以種。",
            "阿松爺爺拿出藏起來的柿子，大家一起吃、一起撒種子，期待長出更多甜柿子。",
        ],
        "story_excerpts": [
            "阿松爺爺家的柿子好甜，可是他一直獨占，還故意在大家面前狼吞虎嚥，讓人只能看著流口水。",
            "哎唷奶奶搬來時稱讚柿子，阿松爺爺卻只給她吃完剩下的柿子蒂。哎唷奶奶仍笑著說謝謝。",
            "隔天，哎唷奶奶和孩子們用柿子蒂打陀螺，玩得很開心。阿松爺爺怕大家來要，急忙把柿子全採下來藏進倉庫。",
            "哎唷奶奶來時，樹上已沒柿子。阿松爺爺改給枯葉，哎唷奶奶和孩子們又把葉子做成項鍊和娃娃。",
            "阿松爺爺再把葉子都打落藏起來，最後連樹枝也給了出去。孩子們用樹枝串麵糰烤麵包，院子裡更熱鬧。",
            "阿松爺爺一急又去砍樹，直到看到只剩樹樁才驚醒，抱著頭大哭：我怎麼會做出這種事。",
            "哎唷奶奶說，如果留一顆柿子，裡面的種子還能拿來種。阿松爺爺立刻拿出倉庫裡好多柿子，請大家吃完把種子到處撒下。",
            "最後大家一起吃甜柿、一起撒種，盼望長出更多柿子。阿松爺爺從獨占慢慢走向分享。",
        ],
        "orid_prompt_bank": {
            "O": [
                "故事一開始，阿松爺爺對柿子是怎麼做的？哪一句或哪個動作看得出來？",
                "阿松爺爺第一次給哎唷奶奶的是什麼？哎唷奶奶怎麼回應？",
                "拿到柿子蒂後，哎唷奶奶和小朋友做了什麼？",
                "阿松爺爺看到孩子們玩柿子蒂後，馬上做了哪件事？",
                "樹上沒有柿子之後，阿松爺爺又拿出什麼給大家？",
                "葉子那一段裡，孩子們把葉子做成了哪些東西？",
                "後來大家又用樹枝做了什麼活動？",
                "阿松爺爺為什麼會去砍樹？砍完後他看到什麼？",
                "哎唷奶奶說了哪句話，讓事情開始轉回來？",
                "最後大家一起做了哪兩件事，讓故事結尾和開頭不一樣？",
                "如果照順序說一次，你會怎麼用「先…再…最後…」整理？",
                "你覺得哪一幕是全書最大轉折？那一幕前後各發生了什麼？",
            ],
            "R": [
                "如果你是看著柿子卻吃不到的孩子，你第一個感覺會是什麼？",
                "當阿松爺爺只給柿子蒂時，你覺得哎唷奶奶心裡比較像哪種感受？",
                "你看到阿松爺爺一直把東西藏起來時，心情是緊張、生氣，還是難過？為什麼？",
                "阿松爺爺發現只剩樹樁那一刻，你覺得他最強烈的感覺是什麼？",
                "故事裡哪一幕讓你最心疼？你心疼的是誰？",
                "哪一幕讓你覺得比較溫暖？是什麼讓你有這種感覺？",
                "如果你在現場，你會先安慰阿松爺爺還是先安慰小朋友？為什麼？",
                "你覺得哎唷奶奶在每次說謝謝時，心裡可能在想什麼？",
                "如果這件事發生在班上，班上同學的情緒可能怎麼變化？",
                "你比較像故事裡哪個角色的心情路線？從哪一幕開始像？",
            ],
            "I": [
                "你覺得這個故事最想提醒我們的一件事是什麼？",
                "為什麼同樣是柿子蒂、葉子、樹枝，在哎唷奶奶手上會變成快樂？",
                "你覺得阿松爺爺真正失去的是柿子，還是別的東西？為什麼？",
                "哎唷奶奶一直說謝謝，這在故事裡有什麼力量？",
                "你怎麼理解「留一顆柿子，留下一個可能」這個想法？",
                "阿松爺爺從獨占到分享，最關鍵的轉折點是哪一幕？",
                "你覺得故事想談的是資源分配、公平，還是人與人的關係？為什麼？",
                "如果把這本書變成一句提醒語，你會寫哪一句？",
                "你認為故事在告訴我們：遇到想獨占時，應該先想哪件事？",
                "你覺得『把好東西變成大家的好』在這本書裡是怎麼被做到的？",
            ],
            "D": [
                "下次你很想把東西留給自己時，你會先做哪一個小動作讓自己停一下？",
                "如果你發現自己像阿松爺爺一樣越藏越緊張，你會先找誰說一聲？",
                "這週你要做一個分享行動的話，會分享什麼、跟誰分享？",
                "遇到誤會時，你會怎麼用一句話先問清楚，不讓衝動變大？",
                "如果班上有人被排除在外，你願意先做哪個小幫忙？",
                "你可以設一個提醒自己不衝動的口訣嗎？",
                "你打算怎麼做，才能把「我的東西」變成「大家都能一起用」？",
                "如果你今天就要練習一次，你第一步會在什麼情境做？",
                "你會用什麼方法檢查自己有沒有真的做到這個行動？",
                "如果今天沒做到，你明天會怎麼調整讓自己比較做得到？",
            ],
        },
        "writing_guide": {
            "O": "客觀：說清楚角色、事件與順序（先…再…最後…），不加評價。",
            "R": "感受：用情緒詞描述心情，並連回一個故事畫面（因為…所以…）。",
            "I": "意義：提出一個提醒/道理，並用故事中的一個轉折當理由。",
            "D": "行動：寫一個可執行的小步驟（下次我會…在…先…再…）。",
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


def resolve_book_pack(pack: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """
    If DB-stored book_pack is older than BOOK_PACK_BY_WEEK for the same title,
    overlay story_excerpts, orid_prompt_bank, and version so RAG/prompts stay current
    without rewriting readings rows.
    """
    if not isinstance(pack, dict) or pack.get("schema") != "book_pack_v1":
        return pack
    title = str(pack.get("book_title") or "").strip()
    default: Optional[dict[str, Any]] = None
    for _w, p in BOOK_PACK_BY_WEEK.items():
        if str(p.get("book_title") or "").strip() == title:
            default = p
            break
    if not default:
        return pack
    try:
        sv = int(pack.get("version") or pack.get("book_pack_version") or 1)
    except (TypeError, ValueError):
        sv = 1
    try:
        dv = int(default.get("version") or 1)
    except (TypeError, ValueError):
        dv = 1
    if sv >= dv:
        return pack
    merged = dict(pack)
    merged["story_excerpts"] = list(default.get("story_excerpts") or [])
    merged["orid_prompt_bank"] = dict(default.get("orid_prompt_bank") or {})
    if default.get("rag_source") and not merged.get("rag_source"):
        merged["rag_source"] = default.get("rag_source")
    if default.get("embedding_bundle_id") and not merged.get("embedding_bundle_id"):
        merged["embedding_bundle_id"] = default.get("embedding_bundle_id")
    if default.get("full_text_path") and not merged.get("full_text_path"):
        merged["full_text_path"] = default.get("full_text_path")
    merged["version"] = dv
    return merged


def _extract_week_from_reading_title(title: str) -> Optional[int]:
    m = re.search(r"第\s*(\d+)\s*週", title or "")
    if not m:
        return None
    try:
        w = int(m.group(1))
        return w if w > 0 else None
    except Exception:
        return None


def load_book_pack_from_reading(reading: Optional[Reading]) -> Optional[dict[str, Any]]:
    if not reading or not (reading.content or "").strip():
        return None
    pack = resolve_book_pack(parse_book_pack(reading.content))
    if not isinstance(pack, dict):
        return pack
    out = dict(pack)
    reading_title = str(reading.title or "")
    out.setdefault("reading_title", reading_title)
    week = _extract_week_from_reading_title(reading_title)
    if week:
        out.setdefault("week", week)
        out.setdefault("embedding_bundle_id", f"week_{week}")
    return out


def build_writing_coach_welcome_text(book_pack: Optional[dict[str, Any]]) -> str:
    title = str((book_pack or {}).get("book_title") or "").strip()
    book = f"《{title}》" if title else "這本書"
    return (
        f"先從左邊任一格開始寫都可以喔！這裡是 {book} 的 ORID 反思。"
        "寫一寫若卡住，按該格的「取得回饋」，我就會在這裡幫你看。"
    )


async def seed_writing_coach_welcome_if_needed(
    db: AsyncSession,
    *,
    session: OridSession,
    reading: Optional[Reading],
) -> None:
    cnt = await db.scalar(
        select(func.count(OridMessage.id)).where(OridMessage.session_id == session.id)
    )
    if (cnt or 0) > 0:
        return
    book_pack = load_book_pack_from_reading(reading)
    text = build_writing_coach_welcome_text(book_pack)
    db.add(OridMessage(session_id=session.id, stage="O", sender="ai", text=text))
    await db.commit()


def book_anchor_one_line(book_pack: Optional[dict[str, Any]], max_len: int = 72) -> str:
    ev = (book_pack or {}).get("key_events") or []
    if not isinstance(ev, list) or not ev:
        return ""
    s = str(ev[0]).strip()
    if not s:
        return ""
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


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
        compact_o = re.sub(r"\s+", "", t)
        if len(compact_o) >= 5:
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
    # Prefer short CJK anchors; avoid echoing random Latin tokens.
    for p in parts:
        if re.search(r"[\u4e00-\u9fff]", p) and 2 <= len(p) <= 10:
            return p[:10]
    t2 = re.sub(r"\s+", "", t)
    m = re.search(r"[\u4e00-\u9fff]{2,10}", t2)
    if m:
        return m.group(0)[:10]
    return ""


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


def _looks_glitched_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    # Obvious malformed output from generation
    if "�" in t:
        return True
    if re.search(r"[，。！？]{2,}", t):
        return True
    # Repeated same Chinese character can create awkward phrases (e.g. 咬咬/問問問)
    for m in re.finditer(r"([\u4e00-\u9fff])\1{1,}", t):
        ch = m.group(1)
        if ch not in {"哈", "呵", "嗯", "啊"}:
            return True
    return False


def _looks_glitched_question(text: str) -> bool:
    q = _sanitize_one_question(text)
    if _looks_glitched_text(q):
        return True
    # Contradictory count phrasing usually indicates a generation glitch.
    if ("第一次" in q and "兩次" in q) or ("一次" in q and "兩次" in q):
        return True
    return False


def _extract_question_sentence(text: str) -> str:
    for s in _split_sentences(text):
        if "？" in s or "?" in s:
            return _sanitize_one_question(s)
    return ""


def _extract_question_snippets_from_ai_text(text: str) -> list[str]:
    """All question sentences in one AI bubble (for anti-repeat)."""
    out: list[str] = []
    for s in _split_sentences(text):
        if "？" in s or "?" in s:
            q = _sanitize_one_question(s)
            if len(re.sub(r"\s+", "", q)) > 4:
                out.append(q)
    if not out and "？" in (text or ""):
        out.append(_sanitize_one_question(text))
    return out


def recent_ai_questions_for_prompt(msgs: list[OridMessage], stage: str, limit: int = 6) -> str:
    s = (stage or "O").strip().upper()
    ai_msgs = [m for m in msgs if (m.stage or "").strip().upper() == s and m.sender == "ai"]
    seen: list[str] = []
    for m in ai_msgs[-12:]:
        for q in _extract_question_snippets_from_ai_text(m.text):
            if q not in seen:
                seen.append(q)
    tail = seen[-limit:]
    if not tail:
        return "（尚無）"
    return "\n".join(f"- {x}" for x in tail)


def latest_ai_question_for_stage(msgs: list[OridMessage], stage: str) -> str:
    s = (stage or "O").strip().upper()
    for m in reversed(msgs):
        if m.sender != "ai":
            continue
        if (m.stage or "").strip().upper() != s:
            continue
        q = _extract_question_sentence(m.text or "")
        if q and (not _looks_glitched_question(q)):
            return _sanitize_one_question(q)
    return ""


def _normalize_question_for_compare(s: str) -> str:
    t = (s or "").strip().replace("?", "？")
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[「」『』\"'，。！？；：、（）]", "", t)
    return t


def _question_similar_to_recent(question: str, recent_block: str) -> bool:
    qn = _normalize_question_for_compare(question)
    if len(qn) < 6:
        return False
    for line in (recent_block or "").split("\n"):
        line = line.strip().lstrip("-").strip()
        if not line or line == "（尚無）":
            continue
        ln = _normalize_question_for_compare(line)
        if len(ln) < 6:
            continue
        if qn == ln:
            return True
        shorter, longer = (qn, ln) if len(qn) <= len(ln) else (ln, qn)
        if len(shorter) >= 8 and shorter in longer:
            return True
        if len(qn) >= 12 and len(ln) >= 12 and qn[:12] == ln[:12]:
            return True
    return False


def pick_non_repeating_fallback_question(
    *,
    stage: str,
    book_pack: Optional[dict[str, Any]],
    student_text: str,
    ai_turn_count_same_stage: int,
    recent_questions_block: str,
    preferred: str,
) -> str:
    """Prefer checker/bank question; if generic or too similar to recent AI questions, rotate."""
    q0 = _sanitize_one_question(preferred)
    if (
        (not _looks_generic_question(q0))
        and (not _question_similar_to_recent(q0, recent_questions_block))
        and (not _looks_glitched_question(q0))
    ):
        return q0
    for offset in range(0, 8):
        raw = pick_prompt_from_bank(book_pack, stage, ai_turn_count_same_stage + 1 + offset)
        cand = _sanitize_one_question(raw)
        if (
            (not _looks_generic_question(cand))
            and (not _question_similar_to_recent(cand, recent_questions_block))
            and (not _looks_glitched_question(cand))
        ):
            return cand
    st = (stage or "O").strip().upper()
    if st == "O":
        for i in range(len(_O_ANGLE_FALLBACKS)):
            cand = _pick_variant(_O_ANGLE_FALLBACKS, f"{student_text}:{ai_turn_count_same_stage}:{i}")
            cq = _sanitize_one_question(cand)
            if not _question_similar_to_recent(cq, recent_questions_block):
                return cq
    return _sanitize_one_question(ai_prompt_by_stage(stage))


def _focus_ack(student_text: str, kind: str = "followup") -> str:
    if kind == "low_effort":
        return _pick_variant(
            [
                "沒關係，你先抓一個小地方說就可以。",
                "不急，先從你最有印象的一幕開始。",
                "沒事，我們換一個更好回答的角度。",
                "沒問題，先從角色或動作挑一個說。",
                "先想一下書裡某一幕，用一句話說也可以。",
                "你可以挑一個記得清楚的細節試著回答。",
            ],
            f"low_effort:{student_text}",
        )
    if kind == "unsafe":
        return _pick_variant(
            [
                "我想跟你好好聊書，但先不要用傷人的話。",
                "我們可以把話說好一點，再把重點放回故事。",
                "先把語氣放輕一點，我們再繼續聊故事。",
            ],
            f"{kind}:{student_text}",
        )

    kw = _extract_keyword(student_text)
    if kw and not _is_low_effort_text(student_text):
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
                "沒關係，我們從故事裡找找線索。",
                "好，那我們一起回到故事看看。",
                "先用書裡的印象回答就可以，不用完整也沒關係。",
                "我們先把這一題說清楚一點。",
                "你可以照自己的說法，把書裡那一幕講出來。",
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
            "先把重點拉回故事這一段。",
            "我們先回到故事裡剛剛發生的事。",
            "先把剛剛的話接回書中的角色和事件。",
            "先照書裡發生的事來想一想。",
            "我們先把這段劇情釐清一下。",
            "不急，先把書裡你看到的那一幕說出來。",
            "先回到教材裡的情節喔。",
            "先把這題用故事裡的事來回答看看。",
        ],
        f"neutral-pullback:{seed}",
    )


def _offtopic_bridge_ack(student_text: str) -> str:
    kw = _extract_keyword(student_text)
    if kw and (not _is_low_effort_text(student_text)):
        return _pick_variant(
            [
                f"{kw}這個話題也有趣，我們先把故事這段聊完。",
                f"我有接到你提到{kw}，先把書裡這一幕走完。",
                f"你剛剛提到{kw}，我們先回到故事主線，等下再延伸。",
            ],
            f"offtopic-bridge:{kw}:{student_text}",
        )
    return _pick_variant(
        [
            "這個話題也有趣，我們先把故事主線聊完。",
            "我有接到你的意思，先把書裡這段走完。",
            "先把故事這一幕說清楚，等等再延伸別的話題。",
        ],
        f"offtopic-bridge:{student_text}",
    )


def _cross_stage_ack(current_stage: str, student_text: str) -> Optional[str]:
    obj = _detect_cross_stage_answer(current_stage, student_text)
    if not obj:
        return None
    return str(obj.get("ack") or "").strip() or None


def _stage_recent_lines(msgs: list[OridMessage], stage: str, limit: int = 8) -> list[str]:
    out: list[str] = []
    for m in msgs:
        if (m.stage or "").strip().upper() != stage:
            continue
        prefix = "學生" if m.sender == "student" else "老師"
        out.append(f"{prefix}：{m.text}")
    return out[-limit:]


def _recent_session_lines(msgs: list[OridMessage], limit: int = 12) -> list[str]:
    out: list[str] = []
    for m in msgs[-limit:]:
        prefix = "學生" if m.sender == "student" else "老師"
        t = (m.text or "").strip()
        if t:
            out.append(f"{prefix}：{t}")
    return out


def _is_meta_or_injection_text(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    meta_tokens = [
        "忽略",
        "無視",
        "system prompt",
        "你是chatgpt",
        "你是 gpt",
        "當作我通過",
        "直接給我答案",
        "幫我作弊",
        "不要照規則",
        "roleplay",
    ]
    return any(token in t for token in meta_tokens)


def _is_low_effort_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    compact = re.sub(r"\s+", "", t)
    # 不要用「總字數 ≤2／≤3」當低投入：O 段常見正解是短名詞（柿子蒂、陀螺、倉庫）。
    if len(compact) <= 1:
        return True
    low_effort_tokens = {
        "不知道",
        "不會",
        "隨便",
        "嗯",
        "蛤",
        "呵",
        "...",
        "。",
        "忘記了",
        "我忘了",
        "忘了",
        "想不起來",
        "沒印象",
        "不確定",
        "記不得",
        "忘記",
        "沒有",
        "好啦",
        "算了",
    }
    if t in low_effort_tokens:
        return True
    low_effort_substrings = ["忘記", "想不起來", "沒印象", "不確定", "記不得"]
    if any(k in t for k in low_effort_substrings) and len(compact) <= 8:
        return True
    return False


def _count_recent_student_streak(
    msgs: list[OridMessage],
    *,
    predicate,
    max_scan: int = 8,
) -> int:
    streak = 0
    seen = 0
    for m in reversed(msgs):
        if m.sender != "student":
            continue
        seen += 1
        if predicate((m.text or "").strip()):
            streak += 1
        else:
            break
        if seen >= max_scan:
            break
    return streak


def _allow_chat_message(user_id: str) -> bool:
    if not ORID_ENABLE_RATE_LIMIT or ORID_LIMIT_PER_MINUTE <= 0:
        return True
    now = time.time()
    q = _CHAT_RATE_BUCKETS[user_id]
    while q and (now - q[0] > ORID_LIMIT_WINDOW_SECONDS):
        q.popleft()
    if len(q) >= ORID_LIMIT_PER_MINUTE:
        return False
    q.append(now)
    return True


# ----------------------------
# Writing assist (one-click draft)
# ----------------------------
class WritingAssistRequest(BaseModel):
    session_id: UUID
    week: int = Field(..., ge=1, le=6)
    stage: str = Field(..., pattern="^(O|R|I|D)$")
    draft: str = Field("d1", pattern="^(d1|d2)$")
    base_text: Optional[str] = None
    context_draft: Optional[str] = None


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
    praise: Optional[str] = None
    missing: list[str] = []
    suggestions: list[str] = []
    example: Optional[str] = None
    improved: Optional[str] = None
    meta: dict[str, Any] = {}


async def _llm_book_grounding_supported(
    *,
    student_text: str,
    stage: str,
    book_pack: Optional[dict[str, Any]],
) -> Optional[bool]:
    """
    Semantic checker: ask LLM if student's claim is supported by BOOK_CONTEXT.
    Returns True/False when parse succeeds; otherwise None for fallback heuristics.
    """
    if client is None:
        return None
    t = (student_text or "").strip()
    if len(t) < 2 or not isinstance(book_pack, dict):
        return None
    sys, user_msg = build_book_grounding_checker_prompts(
        student_text=t,
        book_pack=book_pack,
        stage=stage,
    )
    try:
        raw = await _chat_completion(
            [
                {"role": "system", "content": sys},
                {"role": "user", "content": user_msg},
            ],
            max_completion_tokens=min(200, OPENAI_MAX_COMPLETION_TOKENS),
            temperature=0,
        )
        obj = parse_book_grounding_checker_json(raw)
        grounded = obj.get("grounded")
        if isinstance(grounded, bool):
            return grounded
        if isinstance(grounded, str):
            g = grounded.strip().lower()
            if g in {"true", "1", "yes"}:
                return True
            if g in {"false", "0", "no"}:
                return False
    except Exception as e:
        print("[book_grounding_checker_failed]", repr(e))
    return None


async def _enforce_feedback_book_grounding(
    student_text: str,
    book_pack: Optional[dict[str, Any]],
    stage: str,
    ok: bool,
    missing: list[str],
    suggestions: list[str],
    *,
    use_llm_checker: bool = False,
) -> Tuple[bool, list[str], list[str]]:
    """
    Ensure feedback path flags likely hallucinations vs book_pack.
    When enabled and available, run semantic LLM checker first; fallback to
    deterministic rules to keep behavior stable without LLM.
    """
    t = (student_text or "").strip()
    if not t or not book_pack:
        return ok, missing, suggestions

    bad = False
    # Deterministic rules decide blocking first. This keeps normal paraphrases
    # from being over-blocked by an LLM grounding false positive.
    bad = looks_likely_factual_mismatch(t, book_pack) or looks_likely_ungrounded_in_book(
        t, book_pack, stage=stage
    )
    if (not bad) and use_llm_checker:
        # LLM checker is advisory for very suspicious story-like claims only.
        suspicious = any(
            k in t
            for k in (
                "死",
                "過世",
                "打",
                "揍",
                "踢",
                "殺",
                "火箭",
                "外星",
                "機器人",
                "總統",
                "Curry",
                "curry",
            )
        )
        if suspicious:
            grounded = await _llm_book_grounding_supported(
                student_text=t,
                stage=stage,
                book_pack=book_pack,
            )
            if grounded is False:
                bad = True
    if not bad:
        return ok, missing, suggestions
    miss = list(missing)
    sug = list(suggestions)
    anchor = "對齊教材"
    if not any(anchor in (m or "") for m in miss):
        miss.insert(
            0,
            "內容需對齊教材：你剛寫的情節不像書裡發生的",
        )
    s0 = (
        "請對照故事摘要，"
        "改用書中真實的人與事件重寫"
    )
    if s0 not in sug:
        sug.insert(0, s0)
    return False, miss[:1], sug[:1]


def _has_feedback_book_grounding_issue(missing: list[str]) -> bool:
    return any("對齊教材" in (m or "") for m in (missing or []))


def _book_grounding_praise(stage: str) -> str:
    s = (stage or "O").strip().upper()
    if s == "O":
        return "你有試著寫出人物和事件，這是 O 段需要的方向；只是情節要再對回書裡。"
    if s == "R":
        return "你有試著寫出自己的感受，這很好；只是原因要再連回書裡真的發生的事。"
    if s == "I":
        return "你有試著寫出想法，這很好；只是道理要再接回書裡真的發生的事。"
    if s == "D":
        return "你有試著寫出下一步，這很好；只是行動要再接回這本書提醒你的地方。"
    return "你有試著寫，我已經看到了；只是內容要再對回書裡。"




def _draft_praise_line(t: str, stage: str) -> str:
    """稱讚要看得出有讀到原文（人／事／感受／行動片語），避免空泛句。"""
    t = (t or "").strip()
    s = (stage or "O").strip().upper()
    zh = _stage_name_zh_for_feedback(s)
    if not t:
        return "願意下筆就很棒，我們先寫一點點。"
    one = t.replace("\n", " ")
    for sep in ("。", "！", "？", "，"):
        if sep in one:
            one = one.split(sep, 1)[0].strip()
            break
    if len(one) > 36:
        one = one[:36] + "…"
    return f"你有寫到「{one}」，看得出你在寫「{zh}」這一段囉。"


def _control_feedback(stage: str, text: str) -> Tuple[bool, list[str], list[str], Optional[str], Optional[str]]:
    """
    無 LLM 時的規則回饋：只給一組「一個主點」的 missing + suggestion，加一句句型支架（example）。
    回傳：(ok, missing[:1], suggestions[:1], example_stem, praise)
    """
    t = (text or "").strip()
    s = (stage or "O").strip().upper()

    def _has_sentence() -> bool:
        return "。" in t or "！" in t or "？" in t

    stem = {
        "O": "故事裡先發生的是……，後來……",
        "R": "我覺得……，因為……",
        "I": "這件事讓我明白……，因為故事裡……",
        "D": "下次遇到……，我會先……",
    }.get(s, "先寫一句你的想法，再補一個小細節。")

    if not t:
        return (
            False,
            ["這一格還是空白喔"],
            ["你可以先從句型起頭，寫一句就好"],
            stem,
            "願意下筆就很棒，我們先寫一點點。",
        )

    prior: list[tuple[str, str]] = []

    if s == "O":
        _feel = ("我覺得", "感到", "很溫暖", "很感人", "感動", "很好", "我喜歡", "讓人")
        _plot = (
            "把",
            "分給",
            "藏",
            "做",
            "最後",
            "然後",
            "一開始",
            "接著",
            "看到",
            "聽到",
            "做了",
            "主角",
            "同學",
            "爺",
            "柿",
        )
        if any(f in t for f in _feel) and not any(p in t for p in _plot) and len(t) < 55:
            prior.append(
                (
                    "這段讀起來比較像感覺；O 段要先把故事裡實際發生的事寫出來",
                    "試試寫：故事裡先發生的是……，他做了……",
                )
            )
        elif len(t) < 12:
            prior.append(("內容還有點短，讀者會看不出故事在演什麼", "多寫一句：是誰？做了什麼？"))
        elif not _has_sentence():
            prior.append(("讀起來還沒用一句話說完一件事", "試著用句號收尾，讓讀者聽得懂一件事講完"))
        elif len(t) < 25:
            prior.append(("事件順序還能再清楚一點", "先發生什麼，後來又怎樣，寫清楚一點"))
    elif s == "R":
        emo_kw = ["開心", "難過", "生氣", "害怕", "擔心", "緊張", "失望", "感動", "驚訝", "不公平", "高興", "難受"]
        if not any(k in t for k in emo_kw):
            prior.append(("還幾乎沒有寫到心情", "用「我覺得__________」寫一個感覺，再接原因也可以"))
        elif "因為" not in t:
            prior.append(("還沒有寫「為什麼」會這樣想", "我覺得__________，因為故事裡__________"))
    elif s == "I":
        meaning = ["學到", "明白", "代表", "提醒", "意義", "價值", "道理", "重要"]
        if any(k in t for k in ["很難過", "很開心", "生氣", "害怕", "高興"]) and "因為" not in t and not any(
            k in t for k in meaning
        ) and len(t) < 40:
            prior.append(
                (
                    "這比較像寫感覺；I 段要寫你從故事裡「明白或學到」什麼",
                    "這件事讓我明白__________，因為__________",
                )
            )
        elif not any(
            k in t for k in ["我覺得", "提醒", "學到", "明白", "道理", "價值", "重要", "意義", "應該"]
        ):
            prior.append(("還沒有寫出你學到或明白什麼", "我學到__________，因為故事裡__________"))
        elif "因為" not in t and "所以" not in t:
            prior.append(("你想到的這個道理，還能加一個小理由", "我會這樣想，是因為故事裡……"))
    else:
        if any(w in t for w in ("更好的人", "變更好", "變成更好", "要更好", "變成好人", "變一個好")) and (
            "我會" not in t
        ) and len(t) < 45:
            prior.append(
                (
                    "這比較像心願；D 段要寫一個你下次能做得出來的小行動",
                    "下次當__________的時候，我會先__________",
                )
            )
        elif "我會" not in t and "下次" not in t:
            prior.append(("還沒有寫出要怎麼做", "用「下次遇到……，我會先……」寫一個小動作"))
        elif len(t) < 20:
            prior.append(
                (
                    "行動還可以更具體一點",
                    "寫一個能馬上做的「第一步」：我打算先……",
                )
            )

    if prior:
        m0, s0 = prior[0]
        miss = [m0]
        sug = [s0]
        ok = False
        praise = _draft_praise_line(t, s)
    else:
        miss = []
        sug = []
        ok = True
        praise = _draft_praise_line(t, s)

    return ok, miss, sug, stem, praise


def _stage_name_zh_for_feedback(stage: str) -> str:
    s = (stage or "O").strip().upper()
    return {"O": "客觀", "R": "感受", "I": "意義", "D": "行動"}.get(s, "這一段")


class GenAIFeedbackOutput(BaseModel):
    ok: bool
    praise: Optional[str] = None
    missing: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    example: Optional[str] = None
    improved: Optional[str] = None


def _normalize_feedback_list(value: Any, *, max_items: int = 3) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for x in value:
            s = str(x).strip()
            if s:
                out.append(s)
        return out[:max_items]
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
) -> Tuple[bool, list[str], list[str], Optional[str], Optional[str], Optional[str]]:
    ok = bool(obj.get("ok", False))
    missing = _normalize_feedback_list(obj.get("missing"), max_items=1)
    suggestions = _normalize_feedback_list(obj.get("suggestions"), max_items=1)

    pr_raw = obj.get("praise")
    praise = str(pr_raw).strip() if pr_raw else None

    example_raw = obj.get("example")
    improved_raw = obj.get("improved")

    example = str(example_raw).strip() if example_raw not in (None, "") else None
    improved = str(improved_raw).strip() if improved_raw not in (None, "") else None

    ctrl: Optional[Tuple[bool, list[str], list[str], Optional[str], Optional[str]]] = None
    if (not missing) and (not suggestions):
        ok2, miss2, sug2, ex2, pr2 = _control_feedback(stage, text)
        ok = ok or ok2
        missing = missing or miss2
        suggestions = suggestions or sug2
        if not example:
            example = ex2
        if not praise:
            praise = pr2
        ctrl = (ok2, miss2, sug2, ex2, pr2)
    if not praise:
        if ctrl:
            praise = ctrl[4]
        else:
            *_, pr2 = _control_feedback(stage, text)
            praise = pr2

    if improved and len(improved) > 120:
        improved = None

    return ok, missing[:1], suggestions[:1], example, improved, praise


async def _genai_feedback(
    *,
    stage: str,
    text: str,
    book_pack: Optional[dict[str, Any]],
) -> Tuple[bool, list[str], list[str], Optional[str], Optional[str], Optional[str]]:
    sys, user_msg = build_genai_feedback_prompts(stage=stage, text=text, book_pack=book_pack)
    if looks_likely_ungrounded_in_book(text, book_pack, stage=stage):
        user_msg = (
            "【系統提示：教材核對】學生草稿中的具體人、事、物看起來無法由故事摘要／摘錄支持。"
            "請將 ok 設為 false；missing 須溫和說明須對齊教材、勿使用書中未出現的人或情節；"
            "suggestions 要引導學生改用摘要已列事件；example 只給問句或句型起頭，improved 填 null，不要代寫整段。\n\n"
            + user_msg
        )

    if client is None:
        ok2, miss2, sug2, ex2, pr2 = _control_feedback(stage, text)
        return ok2, miss2, sug2, ex2, None, pr2

    kwargs = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": sys},
            {"role": "user", "content": user_msg},
        ],
        "response_format": GenAIFeedbackOutput,
    }
    kwargs["max_completion_tokens"] = ORID_FEEDBACK_MAX_COMPLETION_TOKENS
    if OPENAI_TEMPERATURE is not None:
        kwargs["temperature"] = OPENAI_TEMPERATURE

    structured_length_limited = False
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
        msg = str(e)
        if "LengthFinishReasonError" in msg or "length limit was reached" in msg:
            structured_length_limited = True
            retry_kwargs = dict(kwargs)
            base_max = retry_kwargs.get("max_completion_tokens")
            try:
                base_val = int(base_max) if base_max is not None else 0
            except (TypeError, ValueError):
                base_val = 0
            retry_kwargs["max_completion_tokens"] = max(
                base_val,
                ORID_FEEDBACK_RETRY_MAX_COMPLETION_TOKENS,
            )
            try:
                resp2 = await client.beta.chat.completions.parse(**retry_kwargs)
                parsed2 = resp2.choices[0].message.parsed
                if parsed2:
                    if hasattr(parsed2, "model_dump"):
                        obj2 = parsed2.model_dump()
                    elif isinstance(parsed2, dict):
                        obj2 = parsed2
                    else:
                        obj2 = getattr(parsed2, "__dict__", {}) or {}
                    return _feedback_from_obj(stage=stage, text=text, obj=obj2)
            except Exception as e2:
                print("[writing_feedback][structured_parse_retry_failed]", repr(e2))

    try:
        manual_max = ORID_FEEDBACK_MAX_COMPLETION_TOKENS
        if structured_length_limited:
            base = int(manual_max) if manual_max is not None else 0
            manual_max = max(base, ORID_FEEDBACK_RETRY_MAX_COMPLETION_TOKENS)
        raw = await _chat_completion(
            [
                {"role": "system", "content": sys},
                {"role": "user", "content": user_msg},
            ],
            max_completion_tokens=manual_max,
            temperature=OPENAI_TEMPERATURE,
        )
        obj = _extract_json_object(raw)
        if obj:
            return _feedback_from_obj(stage=stage, text=text, obj=obj)
    except Exception as e:
        print("[writing_feedback][manual_json_failed]", repr(e))

    ok2, miss2, sug2, ex2, pr2 = _control_feedback(stage, text)
    return ok2, miss2, sug2, ex2, None, pr2


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
    await seed_writing_coach_welcome_if_needed(db, session=s, reading=reading)
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
            rr0 = await db.execute(select(Reading).filter(Reading.id == session.reading_id))
            reading0 = rr0.scalars().first()
            await seed_writing_coach_welcome_if_needed(db, session=session, reading=reading0)
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
    await seed_writing_coach_welcome_if_needed(db, session=new_session, reading=reading)
    return new_session


@router.post("/writing-coach/chat", response_model=WritingCoachChatResponse)
async def writing_coach_chat(
    data: WritingCoachChatRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    r = await db.execute(select(OridSession).filter(OridSession.id == data.session_id))
    session = r.scalars().first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    rr = await db.execute(select(Reading).filter(Reading.id == session.reading_id))
    reading = rr.scalars().first()
    book_pack = load_book_pack_from_reading(reading)

    stage_ctx = (data.stage or "O").strip().upper()
    draft_key = (data.draft or "d1").strip().lower()
    if draft_key not in ("d1", "d2"):
        draft_key = "d1"
    source = (data.source or "free_text").strip().lower()
    body = (data.student_text or "").strip()

    if source == "feedback_button" and not body:
        raise HTTPException(status_code=400, detail="student_text is empty for feedback_button")

    if not _allow_chat_message(str(user.id)):
        msg = "請慢一點，我們一次說一個重點。"
        db.add(OridMessage(session_id=session.id, stage=stage_ctx, sender="ai", text=msg))
        await db.commit()
        return WritingCoachChatResponse(
            session_id=session.id,
            ai_reply=msg,
            stage=stage_ctx,
            meta={"rate_limited": True},
        )

    if source == "feedback_button":
        display_student = f"[{stage_ctx} {_draft_label_zh(draft_key)}]\n{body}"
    else:
        display_student = body
        if not display_student:
            raise HTTPException(status_code=400, detail="student_text is empty")

    db.add(OridMessage(session_id=session.id, stage=stage_ctx, sender="student", text=display_student))
    await db.commit()

    q = await db.execute(
        select(OridMessage)
        .filter(OridMessage.session_id == session.id)
        .order_by(OridMessage.created_at.asc())
    )
    msgs = list(q.scalars().all())

    condition = normalize_orid_condition(session.condition, default=DEFAULT_ORID_CONDITION)
    fb_ok: Optional[bool] = None
    fb_missing: list[str] = []
    fb_sug: list[str] = []
    fb_ex: Optional[str] = None
    fb_imp: Optional[str] = None
    fb_praise: Optional[str] = None
    coach_meta: dict[str, Any] = {}

    if source == "feedback_button":
        anchor_line = book_anchor_one_line(book_pack)
        if is_control_condition(condition, default=DEFAULT_ORID_CONDITION):
            fb_ok, fb_missing, fb_sug, fb_ex, fb_praise = _control_feedback(stage_ctx, body)
            fb_imp = None
        else:
            fb_ok, fb_missing, fb_sug, fb_ex, fb_imp, fb_praise = await _genai_feedback(
                stage=stage_ctx, text=body, book_pack=book_pack
            )

        fb_ok, fb_missing, fb_sug = await _enforce_feedback_book_grounding(
            body,
            book_pack,
            stage_ctx,
            bool(fb_ok),
            fb_missing,
            fb_sug,
            use_llm_checker=(not is_control_condition(condition, default=DEFAULT_ORID_CONDITION)),
        )
        if _has_feedback_book_grounding_issue(fb_missing):
            fb_praise = _book_grounding_praise(stage_ctx)

        if is_control_condition(condition, default=DEFAULT_ORID_CONDITION):
            ai_reply = format_control_feedback_reply(
                ok=bool(fb_ok),
                missing=fb_missing,
                suggestions=fb_sug,
                stage=stage_ctx,
                book_anchor=anchor_line,
                praise=fb_praise,
                student_draft=body,
            )
        elif client is None:
            ai_reply = format_control_feedback_reply(
                ok=bool(fb_ok),
                missing=fb_missing,
                suggestions=fb_sug,
                stage=stage_ctx,
                book_anchor=anchor_line,
                praise=fb_praise,
                student_draft=body,
            )
        else:
            summary = json.dumps(
                {
                    "ok": fb_ok,
                    "praise": fb_praise,
                    "missing": fb_missing,
                    "suggestions": fb_sug,
                    "example": fb_ex,
                    "improved": fb_imp,
                },
                ensure_ascii=False,
            )
            sys_n, user_n = build_feedback_narration_prompt(
                stage=stage_ctx, feedback_json_summary=summary
            )
            try:
                ai_reply = await _chat_completion(
                    [
                        {"role": "system", "content": sys_n},
                        {"role": "user", "content": user_n},
                    ],
                    max_completion_tokens=min(400, OPENAI_MAX_COMPLETION_TOKENS),
                    temperature=ORID_FOLLOWUP_TEMPERATURE,
                )
            except Exception:
                ai_reply = format_control_feedback_reply(
                    ok=bool(fb_ok),
                    missing=fb_missing,
                    suggestions=fb_sug,
                    stage=stage_ctx,
                    book_anchor=anchor_line,
                    praise=fb_praise,
                    student_draft=body,
                )
            if not (ai_reply or "").strip():
                ai_reply = format_control_feedback_reply(
                    ok=bool(fb_ok),
                    missing=fb_missing,
                    suggestions=fb_sug,
                    stage=stage_ctx,
                    book_anchor=anchor_line,
                    praise=fb_praise,
                    student_draft=body,
                )

        if data.save_feedback:
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
                stage=stage_ctx,
                draft=draft_key,
                text=body,
                ok=bool(fb_ok),
                missing=fb_missing,
                suggestions=fb_sug,
                example=fb_ex,
                improved=fb_imp,
                empty_factory=_ensure_orid_writing_v1,
                praise=fb_praise,
            )
            content_str = json.dumps(obj, ensure_ascii=False)
            saved_wid: Optional[str] = None
            if w:
                w.content = content_str
                await db.commit()
                await db.refresh(w)
                saved_wid = str(w.id)
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
                saved_wid = str(new_w.id)
            if saved_wid:
                coach_meta["saved_to_writing_id"] = saved_wid
    else:
        if is_control_condition(condition, default=DEFAULT_ORID_CONDITION):
            ai_reply = format_control_free_text_reply(stage_ctx)
        else:
            book_context = build_book_context_block(book_pack)
            sys_p = build_writing_coach_system_prompt(
                stage=stage_ctx,
                book_context=book_context,
                source=source,
            )
            hist: list[dict[str, str]] = []
            for m in msgs[-ORID_HISTORY_LIMIT:]:
                role = "user" if m.sender == "student" else "assistant"
                hist.append({"role": role, "content": str(m.text or "")})
            oa_messages: list[dict[str, str]] = [{"role": "system", "content": sys_p}]
            oa_messages.extend(hist)
            try:
                ai_reply = await _chat_completion(
                    oa_messages,
                    max_completion_tokens=OPENAI_MAX_COMPLETION_TOKENS,
                    temperature=OPENAI_TEMPERATURE if OPENAI_TEMPERATURE is not None else ORID_MAIN_FALLBACK_TEMPERATURE,
                )
            except Exception:
                ai_reply = "我這邊有點忙不過來，你先儲存草稿，等一下再試試看。"
            if not (ai_reply or "").strip():
                ai_reply = "我有看到你的訊息，你可以再具體說一下想改哪一句嗎？"

    db.add(OridMessage(session_id=session.id, stage=stage_ctx, sender="ai", text=ai_reply.strip()))
    await db.commit()

    print(
        "[writing_coach_chat]",
        json.dumps(
            {
                "session_id": str(session.id),
                "stage": stage_ctx,
                "source": source,
                "condition": condition,
            },
            ensure_ascii=False,
        ),
    )

    coach_meta.update({"condition": condition, "source": source, "draft": draft_key})
    return WritingCoachChatResponse(
        session_id=session.id,
        ai_reply=ai_reply.strip(),
        stage=stage_ctx,
        feedback_ok=fb_ok,
        feedback_praise=fb_praise,
        feedback_missing=fb_missing,
        feedback_suggestions=fb_sug,
        feedback_example=fb_ex,
        feedback_improved=fb_imp,
        meta=coach_meta,
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
    book_pack = load_book_pack_from_reading(reading)

    q = await db.execute(
        select(OridMessage)
        .filter(OridMessage.session_id == session.id)
        .order_by(OridMessage.created_at.asc())
    )
    msgs = q.scalars().all()

    if (data.context_draft or "").strip():
        stage_history = [f"學生目前在此段的草稿：\n{(data.context_draft or '').strip()[:1500]}"]
    else:
        stage_history = _recent_session_lines(msgs, limit=12)
        if not stage_history:
            stage_history = ["(尚無回饋對話，請學生先寫幾句或與寫作教練聊聊)"]

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
    book_pack = load_book_pack_from_reading(reading)

    text = (data.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")

    condition = normalize_orid_condition(session.condition, default=DEFAULT_ORID_CONDITION)

    praise: Optional[str] = None
    if is_control_condition(condition, default=DEFAULT_ORID_CONDITION):
        ok, missing, suggestions, _, praise = _control_feedback(data.stage, text)
        example = None
        improved = None
    else:
        ok, missing, suggestions, example, improved, praise = await _genai_feedback(
            stage=data.stage, text=text, book_pack=book_pack
        )

    ok, missing, suggestions = await _enforce_feedback_book_grounding(
        text,
        book_pack,
        data.stage,
        bool(ok),
        missing,
        suggestions,
        use_llm_checker=(not is_control_condition(condition, default=DEFAULT_ORID_CONDITION)),
    )
    if _has_feedback_book_grounding_issue(missing):
        praise = _book_grounding_praise(data.stage)

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
            praise=praise,
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
        praise=praise,
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
