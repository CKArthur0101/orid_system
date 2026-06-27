from __future__ import annotations

from uuid import UUID, uuid4
from typing import Optional, Any, Tuple, List, Dict
from dataclasses import dataclass
import os
import re
import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from pydantic import BaseModel, Field
from openai import AsyncOpenAI, BadRequestError

from app.database import get_async_session, User
from app.users import current_active_user
from app.models import Reading, OridSession, OridChatMessage, OridWeekSubmission, OridStageAttempt, OridFeedbackEvent, OridBadgeEvent
from app.schemas import (
    ReadingCreate, ReadingRead,
    OridSessionCreate, OridSessionRead,
    OridWritingCreate, OridWritingUpdate, OridWritingRead,
    OridMessageRead,
    OridMeCapabilitiesRead,
    WritingCoachChatRequest,
    WritingCoachChatResponse,
    PromptUsageRequest,
    PromptUsageResponse,
    OridProgressRead,
)

router = APIRouter(tags=["orid"])
logger = logging.getLogger(__name__)

# ----------------------------
# Prompt bank & Checker
# ----------------------------
PROMPTS_OK = True
PROMPTS_IMPORT_ERROR: Optional[str] = None
CHECKER_OK = True
CHECKER_IMPORT_ERROR: Optional[str] = None

from app.prompts.shared_parts.book_context import build_book_context_block
from app.prompts.builders.writing_feedback import build_genai_feedback_prompts
from app.prompts.builders.writing_assist import build_writing_d1_prompts, build_writing_d2_prompts
from app.prompts.parsers.writing_assist import parse_writing_assist_response
from app.prompts.builders.coach_chat import (
    build_feedback_narration_prompt,
    build_synthesis_coach_system_prompt,
    build_writing_coach_system_prompt,
)
from app.prompts.playbook_variants import pick_variant
from app.utils import strip_markdown_for_student_chat
from app.services.orid_rubric_scoring import (
    apply_single_level_estimate,
    calculate_orid_sel_score,
    clamp_total_score,
    collect_levels_from_writing_obj,
    extract_orid_levels_from_rubric_meta,
)
from app.services.orid_badges import (
    calculate_earned_badges,
    get_new_badges,
    get_earned_badges_from_db,
    load_session_progress,
    record_badge_events,
    update_session_score_snapshot,
)
from app.prompts.policy.student_input_bucket import (
    classify_student_input,
    skip_book_grounding_enforcement,
    truncate_student_draft_excerpt,
)
from app.prompts.policy.feedback_focus import (
    apply_o_key_event_gaps,
    detect_feedback_strength,
    normalize_feedback_focus,
)
from app.prompts.policy.control_feedback import (
    format_control_feedback_reply,
    format_control_free_text_reply,
)
from app.prompts.policy.scaffold_guard import (
    scaffold_feedback_example,
    scaffold_feedback_suggestions,
)
from app.content.rubrics import WEEK1_ORID_RUBRIC, WEEK1_SEL_RUBRIC
from app.prompts.policy.turn_destination import (
    CONTROL_O_META_MISSING,
    CONTROL_O_META_SUGGESTION,
    is_o_placeholder_or_stuck_draft,
    personalized_control_praise_line,
    strip_orid_stage_tag,
    student_o_meta_stuck,
)
from app.prompts.builders.checker import build_book_grounding_checker_prompts
from app.prompts.policy.grounding import (
    extract_unsupported_action_phrase,
    extract_wrong_concrete_noun,
    book_contrast_noun_for,
    looks_story_related_to_book,
    looks_obviously_offtopic,
    looks_likely_factual_mismatch,
    looks_likely_ungrounded_in_book,
)
from app.prompts.parsers.json_payloads import (
    extract_json_object,
    parse_book_grounding_checker_json,
)
from app.services.safety import check_safety
from app.services.orid_condition import normalize_orid_condition, is_control_condition
from app.services.orid_writing_store import (
    ensure_orid_writing_obj,
    merge_synthesis_feedback_into_writing,
    upsert_feedback_into_stage,
)
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
# 第二段 LLM（JSON→三段敘述）：預設給比 400 稍多空間，較能帶進書中具體情節（仍受 OPENAI_MAX_COMPLETION_TOKENS 上限）。
ORID_FEEDBACK_NARRATION_MAX_COMPLETION_TOKENS = int(
    os.getenv("ORID_FEEDBACK_NARRATION_MAX_COMPLETION_TOKENS", "420")
)
ORID_OFFTOPIC_STRICT = _env_bool("ORID_OFFTOPIC_STRICT", False)
ORID_FEEDBACK_INTERNAL_PLANNER = _env_bool("ORID_FEEDBACK_INTERNAL_PLANNER", False)
ORID_CHAT_PROMPT_VERSION = os.getenv("ORID_CHAT_PROMPT_VERSION", "orid-chat-v2.2")
ORID_LIMIT_PER_MINUTE = int(os.getenv("ORID_LIMIT_PER_MINUTE", "30"))
ORID_LIMIT_WINDOW_SECONDS = int(os.getenv("ORID_LIMIT_WINDOW_SECONDS", "60"))
ORID_MAIN_FALLBACK_TEMPERATURE = float(os.getenv("ORID_MAIN_FALLBACK_TEMPERATURE", "0.9"))

ORID_ALLOW_HEURISTIC_PASS = _env_bool("ORID_ALLOW_HEURISTIC_PASS", False)
ORID_ENABLE_RATE_LIMIT = _env_bool("ORID_ENABLE_RATE_LIMIT", True)


def _draft_label_zh(draft: str) -> str:
    return "草稿1" if (draft or "").strip().lower() == "d1" else "草稿2"


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


def _user_role(user: User) -> str:
    return str(getattr(user, "role", "student") or "student").strip().lower()


def _is_teacher_or_admin(user: User) -> bool:
    return _user_role(user) in {"teacher", "admin"}


def _require_teacher_or_admin(user: User) -> None:
    if not _is_teacher_or_admin(user):
        raise HTTPException(status_code=403, detail="權限不足")


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
        "version": 4,
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
        "writing_rubric": WEEK1_ORID_RUBRIC,
        "sel_rubric": WEEK1_SEL_RUBRIC,
    }
}


def _default_reading_content_for_week(week: int) -> str:
    pack = BOOK_PACK_BY_WEEK.get(week)
    if pack:
        return json.dumps(pack, ensure_ascii=False)
    return "先用測試文字，之後再換正式教材。"


DEFAULT_READING_CONTENT_BY_WEEK = {1: _default_reading_content_for_week(1)}
DEFAULT_ORID_CONDITION = os.getenv("ORID_DEFAULT_CONDITION", "genai")


def book_unit_from_week(week: int) -> int:
    """週 1–2 → 1，3–4 → 2，5–6 → 3（兩週一書同一 session）。"""
    if week < 1 or week > 6:
        raise HTTPException(status_code=400, detail="week must be 1..6")
    return (week + 1) // 2


def _parse_force_new_allowlist() -> set[str]:
    from app.config import settings

    raw = (settings.ORID_FORCE_NEW_ALLOWLIST or "").strip()
    if not raw:
        raw = (os.getenv("ORID_FORCE_NEW_ALLOWLIST", "") or "").strip()
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def _email_allowed_force_new(email: str | None) -> bool:
    """清單為空時：任何人都不可 force_new。清單非空時僅列名 email 可用。"""
    allow = _parse_force_new_allowlist()
    if not allow:
        return False
    e = (email or "").strip().lower()
    return bool(e) and e in allow


def _user_can_force_new(user: User) -> bool:
    """重新開始本週：admin / is_superuser，或 ORID_FORCE_NEW_ALLOWLIST 內的登入帳號。"""
    if getattr(user, "is_superuser", False):
        return True
    if _user_role(user) == "admin":
        return True
    return _email_allowed_force_new(getattr(user, "email", None))


async def _get_or_create_reading_for_week(db: AsyncSession, week: int) -> Reading:
    title = DEFAULT_READING_TITLE_TEMPLATE.format(week=week)
    r_stmt = (
        select(Reading)
        .where(Reading.title == title)
        .order_by(Reading.created_at.desc())
        .limit(1)
    )
    r_res = await db.execute(r_stmt)
    reading = r_res.scalars().first()
    if reading:
        return reading
    content = DEFAULT_READING_CONTENT_BY_WEEK.get(week, _default_reading_content_for_week(week))
    reading = Reading(title=title, content=content)
    db.add(reading)
    await db.commit()
    await db.refresh(reading)
    return reading


def _week_from_reading_title(title: str | None) -> Optional[int]:
    if not title:
        return None
    m = re.search(r"第\s*(\d+)\s*週", str(title))
    if not m:
        return None
    try:
        w = int(m.group(1))
        if 1 <= w <= 6:
            return w
    except (TypeError, ValueError):
        pass
    return None


def _orid_stage_d1_from_writing_content(raw: str | None) -> dict[str, str]:
    out: dict[str, str] = {"O": "", "R": "", "I": "", "D": ""}
    if not raw:
        return out
    try:
        obj = json.loads(raw)
    except Exception:
        return out
    stages = obj.get("stages") if isinstance(obj, dict) else None
    if not isinstance(stages, dict):
        return out
    for k in out:
        st = stages.get(k)
        if isinstance(st, dict):
            out[k] = str(st.get("d1", "") or "")
    return out


async def _fetch_latest_writing_content_for_week(
    db: AsyncSession,
    user_id: UUID,
    session_id: UUID,
    week: int,
) -> Optional[str]:
    w_stmt = select(OridWeekSubmission).where(
        OridWeekSubmission.user_id == user_id,
        OridWeekSubmission.session_id == session_id,
        OridWeekSubmission.week == week,
    )
    w_res = await db.execute(w_stmt)
    w = w_res.scalars().first()
    if not w or w.content is None:
        return None
    return str(w.content)


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
    merged = dict(pack)
    if len(merged.get("key_events") or []) < 3:
        merged["key_events"] = list(default.get("key_events") or [])
    if len(merged.get("story_excerpts") or []) < 3:
        merged["story_excerpts"] = list(default.get("story_excerpts") or [])
    if not merged.get("characters"):
        merged["characters"] = list(default.get("characters") or [])
    if not merged.get("setting"):
        merged["setting"] = list(default.get("setting") or [])
    if not merged.get("core_theme"):
        merged["core_theme"] = list(default.get("core_theme") or [])
    try:
        sv = int(merged.get("version") or merged.get("book_pack_version") or 1)
    except (TypeError, ValueError):
        sv = 1
    try:
        dv = int(default.get("version") or 1)
    except (TypeError, ValueError):
        dv = 1
    needs_rubric_overlay = bool(default.get("sel_rubric") and not merged.get("sel_rubric"))
    if sv >= dv and not needs_rubric_overlay:
        return merged
    merged = dict(merged)
    merged["story_excerpts"] = list(default.get("story_excerpts") or [])
    merged["orid_prompt_bank"] = dict(default.get("orid_prompt_bank") or {})
    if default.get("writing_rubric"):
        merged["writing_rubric"] = default["writing_rubric"]
    if default.get("sel_rubric"):
        merged["sel_rubric"] = default["sel_rubric"]
    if default.get("writing_guide"):
        merged["writing_guide"] = default["writing_guide"]
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
        default_week = BOOK_PACK_BY_WEEK.get(week)
        if isinstance(default_week, dict):
            out = resolve_book_pack({**default_week, **out, "reading_title": reading_title, "week": week})
    return out


LEGACY_WRITING_COACH_WELCOME_SNIPPET = "先從左邊任一格"


def build_writing_coach_welcome_text(book_pack: Optional[dict[str, Any]]) -> str:
    title = str((book_pack or {}).get("book_title") or "").strip()
    book = f"《{title}》" if title else "這本書"
    return (
        "哈囉！我是你的寫作小幫手 🤖\n"
        f"左邊四格，你想先寫哪一格都可以喔！我們一起來想想讀{book}的心得。\n"
        "寫不出來的時候，按那一格的「取得回饋」，我就會在這裡陪你喔！"
    )


async def seed_writing_coach_welcome_if_needed(
    db: AsyncSession,
    *,
    session: OridSession,
    reading: Optional[Reading],
) -> None:
    book_pack = load_book_pack_from_reading(reading)
    text = build_writing_coach_welcome_text(book_pack)
    cnt = await db.scalar(
        select(func.count(OridChatMessage.id)).where(OridChatMessage.session_id == session.id)
    )
    if (cnt or 0) == 0:
        db.add(OridChatMessage(session_id=session.id, stage="O", sender="ai", text=text))
        await db.commit()
        return
    if (cnt or 0) == 1:
        legacy = await db.scalar(
            select(OridChatMessage)
            .where(OridChatMessage.session_id == session.id)
            .where(OridChatMessage.sender == "ai")
            .limit(1)
        )
        if legacy and LEGACY_WRITING_COACH_WELCOME_SNIPPET in str(legacy.text or ""):
            legacy.text = text
            await db.commit()


def book_anchor_one_line(book_pack: Optional[dict[str, Any]], max_len: int = 72) -> str:
    """給控制組／試試看：優先用 key_events，其次摘錄一句，最後用書名引導。"""
    ev = (book_pack or {}).get("key_events") or []
    if isinstance(ev, list) and ev:
        s = str(ev[0]).strip()
        if s:
            return s[: max_len - 1] + "…" if len(s) > max_len else s
    ex = (book_pack or {}).get("story_excerpts") or []
    if isinstance(ex, list):
        for item in ex:
            t = ""
            if isinstance(item, dict):
                t = str(item.get("text") or "").strip()
            else:
                t = str(item).strip()
            if t and "（無文字）" not in t:
                return t[: max_len - 1] + "…" if len(t) > max_len else t
    title = str((book_pack or {}).get("book_title") or "").strip()
    if title:
        tip = f"《{title}》故事開頭，主角做的一件小事"
        return tip[: max_len - 1] + "…" if len(tip) > max_len else tip
    return ""


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


def recent_ai_questions_for_prompt(msgs: list[OridChatMessage], stage: str, limit: int = 6) -> str:
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


def latest_ai_question_for_stage(msgs: list[OridChatMessage], stage: str) -> str:
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


def _stage_recent_lines(msgs: list[OridChatMessage], stage: str, limit: int = 8) -> list[str]:
    out: list[str] = []
    for m in msgs:
        if (m.stage or "").strip().upper() != stage:
            continue
        prefix = "學生" if m.sender == "student" else "老師"
        out.append(f"{prefix}：{m.text}")
    return out[-limit:]


def _recent_session_lines(msgs: list[OridChatMessage], limit: int = 12) -> list[str]:
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
    msgs: list[OridChatMessage],
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


async def _allow_chat_message(db: AsyncSession, user_id: UUID) -> bool:
    if not ORID_ENABLE_RATE_LIMIT or ORID_LIMIT_PER_MINUTE <= 0:
        return True

    window_start = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=max(1, ORID_LIMIT_WINDOW_SECONDS))
    res = await db.execute(
        select(func.count(OridChatMessage.id))
        .join(OridSession, OridSession.id == OridChatMessage.session_id)
        .where(
            OridSession.user_id == user_id,
            OridChatMessage.sender == "student",
            OridChatMessage.created_at >= window_start,
        )
    )
    recent_count = int(res.scalar() or 0)
    return recent_count < ORID_LIMIT_PER_MINUTE


async def _load_recent_session_messages(
    db: AsyncSession,
    session_id: UUID,
    *,
    limit: int,
) -> list[OridChatMessage]:
    recent_q = (
        select(OridChatMessage)
        .filter(OridChatMessage.session_id == session_id)
        .order_by(OridChatMessage.created_at.desc())
        .limit(max(1, limit))
    )
    recent_res = await db.execute(recent_q)
    return list(reversed(recent_res.scalars().all()))


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

    draft_text, tips = parse_writing_assist_response(raw)
    return WritingAssistResponse(stage=stage, draft=draft, draft_text=draft_text, tips=tips)


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


@dataclass
class BookGroundingCheck:
    grounded: Optional[bool]
    unsupported_span: str = ""
    reason: str = ""


async def _llm_book_grounding_check(
    *,
    student_text: str,
    stage: str,
    book_pack: Optional[dict[str, Any]],
) -> Optional[BookGroundingCheck]:
    """
    Semantic checker: ask LLM if student's claim is supported by BOOK_CONTEXT.
    Returns None when API unavailable or parse fails (caller may use heuristics).
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
        grounded_raw = obj.get("grounded")
        grounded: Optional[bool] = None
        if isinstance(grounded_raw, bool):
            grounded = grounded_raw
        elif isinstance(grounded_raw, str):
            g = grounded_raw.strip().lower()
            if g in {"true", "1", "yes"}:
                grounded = True
            elif g in {"false", "0", "no"}:
                grounded = False
        if grounded is None:
            return None
        span = str(obj.get("unsupported_span") or "").strip()
        reason = str(obj.get("reason") or "").strip()
        return BookGroundingCheck(grounded=grounded, unsupported_span=span, reason=reason)
    except Exception:
        logger.warning("book grounding checker failed")
    return None


async def _llm_book_grounding_supported(
    *,
    student_text: str,
    stage: str,
    book_pack: Optional[dict[str, Any]],
) -> Optional[bool]:
    check = await _llm_book_grounding_check(
        student_text=student_text,
        stage=stage,
        book_pack=book_pack,
    )
    return check.grounded if check is not None else None


def _genai_grounding_user_hint(
    check: BookGroundingCheck,
    book_pack: Optional[dict[str, Any]],
) -> str:
    span = (check.unsupported_span or "").strip() or "（書外情節）"
    ref = _book_grounding_reference_line(book_pack)
    ref_line = f"書裡可對照的一句：「{ref}」。" if ref else ""
    reason = (check.reason or "").strip()
    reason_line = f"核對說明：{reason}。" if reason else ""
    return (
        "【教材核對結果（極重要）】學生草稿中有書裡沒有的具體情節。\n"
        f"疑似書外片段：「{span}」。{reason_line}{ref_line}\n"
        "請 ok=false。missing 用**口語**溫和指出哪個詞或哪件事不在書裡，並自然帶一句書裡真的情況；"
        "**禁止**只寫「對齊教材」或「請把內容對齊教材」。"
        "suggestions 用**一個**問句引導學生改寫；example 只給句型支架，improved 填 null。\n\n"
    )


async def _llm_natural_grounding_correction(
    *,
    student_text: str,
    stage: str,
    book_pack: Optional[dict[str, Any]],
    check: BookGroundingCheck,
) -> Optional[Tuple[str, str]]:
    """Generate student-facing missing + suggestion when checker found ungrounded content."""
    if client is None:
        return None
    t = (student_text or "").strip()
    if not t or not isinstance(book_pack, dict):
        return None
    span = (check.unsupported_span or "").strip()
    book_context = build_book_context_block(book_pack, max_events=6, max_chars=1400)
    stage_u = (stage or "O").strip().upper()
    sys = f"""
你是國小五、六年級的寫作回饋助手。
學生寫的內容有部分無法由教材支持；請產生**自然、口語**的糾正，不要像系統模板。

輸出純 JSON：
{{
  "missing": string,
  "suggestions": string
}}

規則：
- missing：只抓**一個**重點；溫和說哪個詞／哪件事不像書裡發生的；可帶一句書裡真的情節對照。
- suggestions：一個短問句或下一步，引導學生改用書裡真的事件再寫。
- 禁止出現「對齊教材」「對照摘要」「掃摘要」。
- 禁止把學生的錯誤情節當成真實發生去追問（例如不要問「為什麼爺爺吃奶奶」）。
- 繁體中文，每欄 1～2 短句，適合國小生。

目前階段：{stage_u}
BOOK_CONTEXT：
{book_context}
""".strip()
    user = (
        f"學生句子：\n{t}\n\n"
        f"疑似書外片段：{span or '（未標出）'}\n"
        f"核對說明：{(check.reason or '').strip() or '（無）'}"
    )
    try:
        raw = await _chat_completion(
            [
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
            max_completion_tokens=min(280, OPENAI_MAX_COMPLETION_TOKENS),
            temperature=0.2,
        )
        obj = parse_book_grounding_checker_json(raw)
        missing = str(obj.get("missing") or "").strip()
        suggestions = str(obj.get("suggestions") or "").strip()
        if missing and suggestions:
            return missing, suggestions
    except Exception:
        logger.warning("natural grounding correction LLM failed")
    return None


def _grounding_fallback_lines(
    *,
    student_text: str,
    book_pack: Optional[dict[str, Any]],
    stage: str,
    check: Optional[BookGroundingCheck] = None,
) -> Tuple[str, str]:
    """Offline / LLM-failure fallback — softer than the old template, for control path."""
    span = (check.unsupported_span if check else "") or extract_unsupported_action_phrase(
        student_text, book_pack
    )
    parts: list[str] = []
    if span:
        parts.append(f"你寫的「{span}」好像不是書裡發生的事")
    wrong_noun = extract_wrong_concrete_noun(student_text, book_pack)
    if wrong_noun:
        contrast = book_contrast_noun_for(wrong_noun, book_pack)
        if contrast:
            parts.append(f"書裡出現的是「{contrast}」，不是「{wrong_noun}」")
        elif wrong_noun not in (span or ""):
            parts.append(f"「{wrong_noun}」這個詞好像不在這本書裡")
    char_note = _book_grounding_character_note(student_text, book_pack)
    if char_note:
        parts.append(char_note)
    ref = _book_grounding_reference_line(book_pack)
    if ref:
        parts.append(f"書裡比較像是「{ref}」")
    if not parts:
        parts.append("你剛寫的情節好像不是書裡發生的事")
    missing = "，".join(parts) + "。"
    stage_upper = (stage or "O").strip().upper()
    suggestion_map = {
        "O": "你可以先想想：書裡是誰、做了什麼？再照那個方向改寫一句。",
        "R": "你可以先想想：書裡哪一幕讓你有這種感覺？再寫你的感受和原因。",
        "I": "你可以先想想：書裡哪件事讓你想到這個道理？再補上故事理由。",
        "D": "你可以先想想：這本書想提醒你什麼？再寫你下次會怎麼做。",
    }
    return missing, suggestion_map.get(stage_upper, "先改用書裡真的人物和事件，再把意思寫清楚。")


def _is_grounding_specific_message(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    cues = (
        "對齊教材",
        "不在書裡",
        "書裡沒有",
        "不是書裡",
        "好像不是書裡",
        "沒有這件事",
        "不像書裡",
        "書裡說的是",
        "書裡比較像是",
        "書中人物是",
        "書裡的人物是",
        "書中叫做",
        "書裡叫做",
        "書裡出現的是",
        "不是「",
        "這個詞好像不在",
    )
    return any(c in t for c in cues)


def _book_grounding_reference_line(book_pack: Optional[dict[str, Any]], max_len: int = 56) -> str:
    if not isinstance(book_pack, dict):
        return ""
    candidates: list[str] = []
    for item in (book_pack.get("key_events") or [])[:3]:
        s = str(item or "").strip()
        if s:
            candidates.append(s)
    for item in (book_pack.get("story_excerpts") or [])[:2]:
        if isinstance(item, dict):
            s = str(item.get("text") or "").strip()
        else:
            s = str(item or "").strip()
        if s:
            candidates.append(s)
    if not candidates:
        return ""
    ref = candidates[0]
    return ref if len(ref) <= max_len else ref[: max_len - 1] + "…"


def _book_grounding_character_note(student_text: str, book_pack: Optional[dict[str, Any]]) -> str:
    t = (student_text or "").strip()
    if not t or not isinstance(book_pack, dict):
        return ""

    characters = book_pack.get("characters") or []
    preferred: dict[str, str] = {}
    for item in characters:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        if name.endswith("爺爺"):
            preferred["爺爺"] = name
        elif name.endswith("奶奶"):
            preferred["奶奶"] = name

    notes: list[str] = []
    for alias, full_name in preferred.items():
        if alias in t and full_name not in t:
            notes.append(f"書裡的人物是「{full_name}」")
    return "，".join(notes[:1])


def _book_grounding_example(stage: str, book_pack: Optional[dict[str, Any]]) -> str:
    s = (stage or "O").strip().upper()
    main_char = ""
    if isinstance(book_pack, dict):
        for item in (book_pack.get("characters") or [])[:3]:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                if name:
                    main_char = name
                    break
    if s == "O":
        if main_char:
            return f"例如：故事的主角是「{main_char}」，一開始……，後來……。"
        return "例如：先寫書裡真的人物，一開始……，後來……。"
    if s == "R":
        return "例如：我看到書裡這一幕時，覺得……，因為……。"
    if s == "I":
        return "例如：這件事讓我明白……，因為書裡……。"
    return "例如：下次遇到類似的情況，我會先……。"


async def _enforce_feedback_book_grounding(
    student_text: str,
    book_pack: Optional[dict[str, Any]],
    stage: str,
    ok: bool,
    missing: list[str],
    suggestions: list[str],
    *,
    use_llm_checker: bool = False,
    input_bucket: Optional[str] = None,
    grounding_check: Optional[BookGroundingCheck] = None,
) -> Tuple[bool, list[str], list[str]]:
    """
    Ensure feedback path flags content not supported by book_pack.

    GenAI path (use_llm_checker=True): LLM checker first; natural correction on failure.
    Control / offline: heuristic rules + softer fallback lines.
    """
    t = (student_text or "").strip()
    if not t or not book_pack:
        return ok, missing, suggestions

    stage_upper = (stage or "O").strip().upper()
    if stage_upper == "D":
        return ok, missing, suggestions

    if input_bucket and skip_book_grounding_enforcement(
        input_bucket, student_text=t, book_pack=book_pack
    ):
        return ok, missing, suggestions

    check = grounding_check
    if use_llm_checker and check is None:
        check = await _llm_book_grounding_check(
            student_text=t,
            stage=stage,
            book_pack=book_pack,
        )

    if use_llm_checker and check is not None:
        if check.grounded is True:
            heuristic_bad = looks_likely_factual_mismatch(t, book_pack) or looks_likely_ungrounded_in_book(
                t, book_pack, stage=stage
            )
            if not heuristic_bad:
                return ok, missing, suggestions
            wrong_noun = extract_wrong_concrete_noun(t, book_pack)
            span = (check.unsupported_span or "").strip() or extract_unsupported_action_phrase(
                t, book_pack
            )
            if wrong_noun and wrong_noun not in span:
                span = span or wrong_noun
            check = BookGroundingCheck(
                grounded=False,
                unsupported_span=span,
                reason=(check.reason or "教材摘錄未支持此說法").strip(),
            )
        if check.grounded is False:
            miss = list(missing)
            sug = list(suggestions)
            if _has_feedback_book_grounding_issue(miss):
                return False, miss[:1], sug[:1]
            natural = await _llm_natural_grounding_correction(
                student_text=t,
                stage=stage,
                book_pack=book_pack,
                check=check,
            )
            if natural:
                miss, sug = [natural[0]], [natural[1]]
            else:
                m_line, s_line = _grounding_fallback_lines(
                    student_text=t,
                    book_pack=book_pack,
                    stage=stage,
                    check=check,
                )
                miss, sug = [m_line], [s_line]
            return False, miss[:1], sug[:1]

    bad = looks_likely_factual_mismatch(t, book_pack) or looks_likely_ungrounded_in_book(
        t, book_pack, stage=stage
    )
    if not bad:
        return ok, missing, suggestions

    miss = list(missing)
    sug = list(suggestions)
    if _has_feedback_book_grounding_issue(miss):
        return False, miss[:1], sug[:1]
    m_line, s_line = _grounding_fallback_lines(
        student_text=t,
        book_pack=book_pack,
        stage=stage,
        check=check,
    )
    return False, [m_line], [s_line]


def _has_feedback_book_grounding_issue(missing: list[str]) -> bool:
    return any(_is_grounding_specific_message(m or "") for m in (missing or []))


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




def _draft_praise_line(text: str, stage: str) -> str:
    """稱讚要看得出有讀到原文（人／事／感受／行動片語），避免空泛句。"""
    raw = (text or "").strip()
    t = strip_orid_stage_tag(raw)
    s = (stage or "O").strip().upper()
    zh = _stage_name_zh_for_feedback(s)
    if not t:
        return "願意下筆就很棒，我們先寫一點點。"
    alt = personalized_control_praise_line(raw, zh)
    if alt:
        return alt
    one = raw.replace("\n", " ")
    for sep in ("。", "！", "？", "，"):
        if sep in one:
            one = one.split(sep, 1)[0].strip()
            break
    if len(one) > 36:
        one = one[:36] + "…"
    return f"你有寫到「{one}」，我有看到你正在寫「{zh}」這一段，方向是對的。"


def _control_feedback(stage: str, text: str) -> Tuple[bool, list[str], list[str], Optional[str], Optional[str]]:
    """
    無 LLM 時的規則回饋：只給一組「一個主點」的 missing + suggestion，加一句句型支架（example）。
    回傳：(ok, missing[:1], suggestions[:1], example_stem, praise)
    """
    raw = (text or "").strip()
    t = strip_orid_stage_tag(raw)
    s = (stage or "O").strip().upper()

    def _has_sentence() -> bool:
        return "。" in t or "！" in t or "？" in t

    stem = {
        "O": "你可以先寫：一開始……，後來……。先把事情照順序講出來就可以了。",
        "R": "你可以先寫：我覺得……，因為……。先寫感受，再補原因。",
        "I": "你可以先寫：這件事讓我明白……，因為……。先寫學到什麼，再補理由。",
        "D": "你可以先寫：下次遇到……，我會先……。先把你做得到的第一步寫出來。",
    }.get(s, "先寫一句你的想法，再補一個小細節。")

    if not t:
        return (
            False,
            ["這一格還是空白喔"],
            ["我們先不用寫很多，你可以先照著句型起頭，寫一句就好。"],
            stem,
            "願意下筆就很棒，我們先寫一點點。",
        )

    prior: list[tuple[str, str]] = []

    if s == "O":
        if student_o_meta_stuck(t):
            prior.append((CONTROL_O_META_MISSING, CONTROL_O_META_SUGGESTION))
        else:
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
                        "這段讀起來比較像在寫感覺；O 段我們先寫故事裡真的發生了什麼事。",
                        "你可以先寫「一開始誰做了什麼」，再補後來發生了什麼。",
                    )
                )
            elif len(t) < 12:
                prior.append(
                    (
                        "內容還有點短，你可以試著多寫一點；也可以先看看下方黃色區塊的句型，跟著接一句就好。",
                        "你可以先寫出故事裡「誰做了什麼」一句，再補「後來……」接下去。",
                    )
                )
            elif not _has_sentence():
                prior.append(
                    (
                        "讀起來還沒用一句話說完一件事",
                        "我們先把同一件事寫成完整一句，再用句號收尾，讓人知道先發生了什麼。",
                    )
                )
            elif len(t) < 25:
                prior.append(
                    ("事件順序還能再清楚一點", "你可以先寫前面發生什麼，再寫後來怎樣，順序會更清楚。")
                )
    elif s == "R":
        emo_kw = ["開心", "難過", "生氣", "害怕", "擔心", "緊張", "失望", "感動", "驚訝", "不公平", "高興", "難受"]
        if not any(k in t for k in emo_kw):
            prior.append(("還幾乎沒有寫到心情", "我們先寫一個明確感受，再補上是故事裡哪一幕讓你有這個感覺。"))
        elif "因為" not in t:
            prior.append(("還沒有寫「為什麼」會這樣想", "你可以把感受後面的原因接上去，讀的人才知道你為什麼會這樣想。"))
    elif s == "I":
        meaning = ["學到", "明白", "代表", "提醒", "意義", "價值", "道理", "重要"]
        if any(k in t for k in ["很難過", "很開心", "生氣", "害怕", "高興"]) and "因為" not in t and not any(
            k in t for k in meaning
        ) and len(t) < 40:
            prior.append(
                (
                    "這比較像寫感覺；I 段我們要寫你從故事裡明白或學到什麼。",
                    "你可以先寫你明白了什麼，再補故事裡哪個地方讓你有這個想法。",
                )
            )
        elif not any(
            k in t for k in ["我覺得", "提醒", "學到", "明白", "道理", "價值", "重要", "意義", "應該"]
        ):
            prior.append(("還沒有寫出你學到或明白什麼", "我們先把你學到的道理講出來，再補故事裡的理由。"))
        elif "因為" not in t and "所以" not in t:
            prior.append(("你想到的這個道理，還能加一個小理由", "你可以再補一句「為什麼會這樣想」，意思就會更完整。"))
    else:
        if any(w in t for w in ("更好的人", "變更好", "變成更好", "要更好", "變成好人", "變一個好")) and (
            "我會" not in t
        ) and len(t) < 45:
            prior.append(
                (
                    "這比較像心願；D 段我們要寫一個你下次做得到的小行動。",
                    "你可以把心願改成一個具體動作，寫出你下次遇到時第一步會怎麼做。",
                )
            )
        elif "我會" not in t and "下次" not in t:
            prior.append(("還沒有寫出要怎麼做", "我們先補一個你真的做得到的小動作，讓讀的人看到你下次會怎麼做。"))
        elif len(t) < 20:
            prior.append(
                (
                    "行動還可以更具體一點",
                    "你可以再寫清楚一點，例如什麼時候做、先做哪一步，行動就會更完整。",
                )
            )

    if prior:
        m0, s0 = prior[0]
        miss = [m0]
        sug = [s0]
        ok = False
        praise = _draft_praise_line(raw, s)
    else:
        miss = []
        sug = []
        ok = True
        praise = _draft_praise_line(raw, s)

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
    # 與 book_pack.writing_rubric 對齊，供後測／分析（可為 null）
    rubric_focus: Optional[str] = None
    rubric_level_estimate: Optional[str] = None


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


def _rubric_meta_from_obj(obj: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rf = obj.get("rubric_focus")
    rl = obj.get("rubric_level_estimate")
    if rf is not None and str(rf).strip():
        out["rubric_focus"] = str(rf).strip()
    if rl is not None and str(rl).strip():
        out["rubric_level_estimate"] = str(rl).strip()
    return out


def _apply_orid_rubric_ok_rule(
    ok: bool,
    rubric_meta: dict[str, Any],
    missing: list[str],
) -> bool:
    """
    V1.2 rule: ORID rubric is the only pass/fail source.
    Level 3/4 means pass unless book grounding already found a factual problem;
    level 1/2 means not pass. SEL guidance never changes this rule.
    """
    if _has_feedback_book_grounding_issue(missing):
        return False
    rl_est = (rubric_meta.get("rubric_level_estimate") or "").strip()
    if not rl_est:
        return bool(ok)
    level = rl_est[:1]
    if level in ("1", "2"):
        return False
    if level in ("3", "4") and not _has_feedback_book_grounding_issue(missing):
        return True
    return bool(ok)


def _feedback_from_obj(
    *,
    stage: str,
    text: str,
    obj: dict[str, Any],
) -> Tuple[bool, list[str], list[str], Optional[str], Optional[str], Optional[str], dict[str, Any]]:
    ok = bool(obj.get("ok", False))
    missing = _normalize_feedback_list(obj.get("missing"), max_items=1)
    suggestions = _normalize_feedback_list(obj.get("suggestions"), max_items=1)
    missing, suggestions = normalize_feedback_focus(
        stage=stage,
        missing=missing,
        suggestions=suggestions,
        student_text=text,
    )

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

    suggestions = scaffold_feedback_suggestions(stage, suggestions[:1])
    example = scaffold_feedback_example(stage, example)

    return ok, missing[:1], suggestions[:1], example, improved, praise, _rubric_meta_from_obj(obj)


def _looks_valid_feedback_narration(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # Keep narration stable: must contain all three required sections.
    required = ("你已經做到", "你可以再加強", "試試看")
    return all(x in t for x in required)


def _prev_ai_opener_from_messages(msgs: list[Any]) -> Optional[str]:
    """Last message is treated as the current student turn; scan earlier AI texts."""
    if not msgs or len(msgs) < 2:
        return None
    for m in reversed(msgs[:-1]):
        if getattr(m, "sender", None) == "ai":
            t = (getattr(m, "text", None) or "").strip()
            if t:
                return t[:24]
    return None


async def _orid_feedback_internal_planner_o(
    *,
    stage: str,
    text: str,
    book_pack: Optional[dict[str, Any]],
    input_bucket: str,
    base_user_msg: str,
) -> str:
    """
    Optional Phase-B path: one unstructured call before structured JSON feedback.
    Gated by ORID_FEEDBACK_INTERNAL_PLANNER; O + meta-stuck + key_events only.
    """
    if not ORID_FEEDBACK_INTERNAL_PLANNER:
        return base_user_msg
    if (stage or "").strip().upper() != "O":
        return base_user_msg
    ke = (book_pack or {}).get("key_events")
    if not isinstance(ke, list) or not ke:
        return base_user_msg
    if not student_o_meta_stuck(text):
        return base_user_msg
    lines = [str(x).strip() for x in ke[:8] if str(x).strip()]
    if not lines:
        return base_user_msg
    ev_text = "\n".join(f"・{x}" for x in lines)
    planner_sys = (
        "你是內部教研備註助理；輸出只給下一個模型看，學生不會直接看到這段。"
        "用繁體中文，3～6 行短句：學生卡在哪、建議優先用哪一個書中事件當接寫錨、一句可照抄接寫的起頭。"
        "不要輸出 JSON，不要寫成整篇教學講稿。"
    )
    planner_user = (
        f"【input_bucket】{input_bucket}\n"
        f"【學生 O 段】\n{text.strip()}\n\n"
        f"【故事摘要關鍵事件】\n{ev_text}\n"
    )
    try:
        note = await _chat_completion(
            [
                {"role": "system", "content": planner_sys},
                {"role": "user", "content": planner_user},
            ],
            max_completion_tokens=400,
            temperature=None,
        )
    except Exception:
        logger.warning("ORID internal feedback planner (O) failed; continuing without note")
        return base_user_msg
    note = (note or "").strip()
    if not note:
        return base_user_msg
    return (
        "【內部分析備註（供你理解學生狀態；你仍必須只輸出規定的 JSON schema）】\n"
        f"{note}\n\n---\n\n"
        + base_user_msg
    )


async def _genai_feedback(
    *,
    stage: str,
    text: str,
    book_pack: Optional[dict[str, Any]],
    input_bucket: str = "normal",
    grounding_check: Optional[BookGroundingCheck] = None,
) -> Tuple[bool, list[str], list[str], Optional[str], Optional[str], Optional[str], dict[str, Any]]:
    sys, user_msg = build_genai_feedback_prompts(
        stage=stage, text=text, book_pack=book_pack, input_bucket=input_bucket
    )
    if grounding_check is not None and grounding_check.grounded is False:
        user_msg = _genai_grounding_user_hint(grounding_check, book_pack) + user_msg
    elif (not skip_book_grounding_enforcement(input_bucket, student_text=text, book_pack=book_pack)) and (stage or "").strip().upper() != "D":
        heuristic_bad = looks_likely_factual_mismatch(text, book_pack) or looks_likely_ungrounded_in_book(
            text, book_pack, stage=stage
        )
        if heuristic_bad:
            span = extract_unsupported_action_phrase(text, book_pack)
            wrong_noun = extract_wrong_concrete_noun(text, book_pack)
            if wrong_noun and wrong_noun not in (span or ""):
                span = span or wrong_noun
            pseudo = BookGroundingCheck(
                grounded=False,
                unsupported_span=span,
                reason="教材摘錄未支持此說法",
            )
            user_msg = _genai_grounding_user_hint(pseudo, book_pack) + user_msg
    elif (not skip_book_grounding_enforcement(input_bucket, student_text=text, book_pack=book_pack)) and client is None and looks_likely_ungrounded_in_book(
        text, book_pack, stage=stage
    ):
        user_msg = (
            "【系統提示：教材核對】學生草稿中的具體人、事、物看起來無法由故事摘要／摘錄支持。"
            "請將 ok 設為 false；missing 須溫和說明哪件事不在書裡；"
            "suggestions 要引導學生改用摘要已列事件；example 只給問句或句型起頭，improved 填 null，不要代寫整段。\n\n"
            + user_msg
        )

    user_msg = await _orid_feedback_internal_planner_o(
        stage=stage,
        text=text,
        book_pack=book_pack,
        input_bucket=input_bucket,
        base_user_msg=user_msg,
    )

    if client is None:
        ok2, miss2, sug2, ex2, pr2 = _control_feedback(stage, text)
        return ok2, miss2, sug2, ex2, None, pr2, {}

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
        logger.warning("writing feedback structured parse failed")
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
            except Exception:
                logger.warning("writing feedback structured parse retry failed")

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
        obj = extract_json_object(raw)
        if obj:
            return _feedback_from_obj(stage=stage, text=text, obj=obj)
    except Exception:
        logger.warning("writing feedback manual json parse failed")

    ok2, miss2, sug2, ex2, pr2 = _control_feedback(stage, text)
    return ok2, miss2, sug2, ex2, None, pr2, {}


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


async def _maybe_advance_stage(
    db: AsyncSession,
    session_id: UUID,
    stage: str,
) -> bool:
    """
    After a feedback event is recorded, check if the student has accumulated
    enough ok=True passes in `stage` to advance current_stage to the next one.
    Does a fresh SELECT of OridSession to avoid reading an expired ORM object
    after a prior commit. Only advances if current_stage still equals `stage`
    (prevents double-advance from concurrent requests).
    Returns True if the stage was advanced.
    """
    required = get_required_pass(stage)
    try:
        # Fresh load — the OridSession object in the caller may be expired
        # after _try_dual_write_feedback's commit.
        sess_res = await db.execute(
            select(OridSession).where(OridSession.id == session_id)
        )
        live_session = sess_res.scalars().first()
        if not live_session:
            return False
        if (live_session.current_stage or "O").strip().upper() != stage.strip().upper():
            return False

        res = await db.execute(
            select(func.count(OridFeedbackEvent.id)).where(
                OridFeedbackEvent.session_id == session_id,
                OridFeedbackEvent.stage == stage,
                OridFeedbackEvent.ok == True,  # noqa: E712
            )
        )
        ok_count = int(res.scalar() or 0)
    except Exception:
        logger.warning("advance stage count failed")
        return False

    if ok_count >= required:
        new_stage = next_stage(stage)
        if new_stage != stage:
            live_session.current_stage = new_stage
            try:
                await db.commit()
                logger.info(
                    "stage advanced",
                    extra={
                        "session_id": str(session_id),
                        "from_stage": stage,
                        "to_stage": new_stage,
                        "ok_count": ok_count,
                        "required": required,
                    },
                )
                return True
            except Exception:
                logger.warning("advance stage commit failed")
                try:
                    await db.rollback()
                except Exception:
                    pass
    return False


async def _try_dual_write_feedback(
    db: AsyncSession,
    *,
    session_id: UUID,
    user_id: UUID,
    stage: str,
    draft: str,
    student_text: str,
    feedback_strength: Optional[str],
    condition: str,
    source: str,
    ok: bool,
    praise: Optional[str],
    missing: list[str],
    suggestions: list[str],
    example: Optional[str],
) -> None:
    """
    Dual-write: record attempt snapshot + structured feedback into analytics tables.
    Wrapped in try/except — never raises, never blocks the main API response.
    """
    try:
        compact = re.sub(r"\s+", "", student_text or "")
        attempt = OridStageAttempt(
            session_id=session_id,
            user_id=user_id,
            stage=stage,
            draft=draft,
            student_text=student_text or "",
            word_count=len(compact),
            feedback_strength=feedback_strength,
            condition=condition,
            source=source,
        )
        db.add(attempt)
        await db.flush()

        event = OridFeedbackEvent(
            attempt_id=attempt.id,
            session_id=session_id,
            user_id=user_id,
            stage=stage,
            draft=draft,
            ok=ok,
            praise=praise,
            missing_json=json.dumps(missing, ensure_ascii=False),
            suggestions_json=json.dumps(suggestions, ensure_ascii=False),
            example=example,
        )
        db.add(event)
        await db.commit()
    except Exception:
        logger.warning("dual write feedback failed")
        try:
            await db.rollback()
        except Exception:
            pass


# ----------------------------
# Routes
# ----------------------------
@router.get("/me/capabilities", response_model=OridMeCapabilitiesRead)
async def orid_me_capabilities(user: User = Depends(current_active_user)):
    return OridMeCapabilitiesRead(orid_can_force_new=_user_can_force_new(user))


@router.post("/readings", response_model=ReadingRead)
async def create_reading(
    data: ReadingCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    _require_teacher_or_admin(user)
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

    wk = _week_from_reading_title(reading.title)
    bu = book_unit_from_week(wk) if wk is not None else None

    s = OridSession(
        user_id=user.id,
        reading_id=data.reading_id,
        condition=normalize_orid_condition(data.condition, default=DEFAULT_ORID_CONDITION),
        current_stage="O",
        stage_turn=0,
        thread_id=None,
        book_unit=bu,
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
    force_new: bool = Query(False, description="true 時強制建立新 session；false 取最近一次（同書單元）。"),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    title = DEFAULT_READING_TITLE_TEMPLATE.format(week=week)
    bu = book_unit_from_week(week)
    user_email = getattr(user, "email", None)

    # Determine the effective condition for this user:
    # admin/test override via URL ?condition=, else use user.orid_condition mapped to session condition.
    def _resolve_condition(url_override: Optional[str]) -> str:
        if url_override and _user_can_force_new(user):
            return normalize_orid_condition(url_override, default=DEFAULT_ORID_CONDITION)
        user_group = str(getattr(user, "orid_condition", "experimental") or "experimental").strip().lower()
        return "genai" if user_group == "experimental" else "control"

    def _session_stale(sess: OridSession) -> bool:
        """True if the user's condition changed after this session was created."""
        updated_at = getattr(user, "orid_condition_updated_at", None)
        if updated_at is None:
            return False
        sess_created = getattr(sess, "created_at", None)
        if sess_created is None:
            return False
        if sess_created.tzinfo is None:
            import pytz
            sess_created = pytz.utc.localize(sess_created)
        return sess_created < updated_at

    if force_new:
        if not _user_can_force_new(user):
            raise HTTPException(status_code=403, detail="force_new 未授權")
        reading = await _get_or_create_reading_for_week(db, week)
        new_condition = _resolve_condition(condition)
        new_session = OridSession(
            user_id=user.id,
            reading_id=reading.id,
            condition=new_condition,
            current_stage="O",
            stage_turn=0,
            thread_id=None,
            book_unit=bu,
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        await seed_writing_coach_welcome_if_needed(db, session=new_session, reading=reading)
        return new_session

    # 同書單元：優先沿用已帶 book_unit 的 session
    s_stmt = (
        select(OridSession)
        .where(OridSession.user_id == user.id, OridSession.book_unit == bu)
        .order_by(OridSession.created_at.desc())
        .limit(1)
    )
    s_res = await db.execute(s_stmt)
    session = s_res.scalars().first()

    reading = await _get_or_create_reading_for_week(db, week)

    if session and not _session_stale(session):
        session.reading_id = reading.id
        await db.commit()
        await db.refresh(session)
        await seed_writing_coach_welcome_if_needed(db, session=session, reading=reading)
        return session

    # 舊資料：依當週 reading title 找的 session（無 book_unit），也要檢查是否過期
    if not session:
        legacy_stmt = (
            select(OridSession)
            .join(Reading, OridSession.reading_id == Reading.id)
            .where(OridSession.user_id == user.id, Reading.title == title)
            .order_by(OridSession.created_at.desc())
            .limit(1)
        )
        s2 = await db.execute(legacy_stmt)
        session = s2.scalars().first()
        if session and not _session_stale(session):
            session.book_unit = bu
            session.reading_id = reading.id
            await db.commit()
            await db.refresh(session)
            await seed_writing_coach_welcome_if_needed(db, session=session, reading=reading)
            return session

    # Create new session (either no existing session, or existing session is stale due to condition change)
    new_condition = _resolve_condition(condition)
    new_session = OridSession(
        user_id=user.id,
        reading_id=reading.id,
        condition=new_condition,
        current_stage="O",
        stage_turn=0,
        thread_id=None,
        book_unit=bu,
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    await seed_writing_coach_welcome_if_needed(db, session=new_session, reading=reading)
    return new_session


@router.get("/progress", response_model=OridProgressRead)
async def get_orid_progress(
    session_id: UUID = Query(...),
    week: int = Query(..., ge=1, le=6),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Return persisted badges and score for the student's session/week."""
    r = await db.execute(select(OridSession).filter(OridSession.id == session_id))
    session = r.scalars().first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    writing_content = await _fetch_latest_writing_content_for_week(
        db, user.id, session.id, week
    )
    progress = await load_session_progress(
        db,
        user_id=user.id,
        session_id=session.id,
        week=week,
        writing_content=writing_content,
        empty_writing_factory=_ensure_orid_writing_v1,
    )
    return OridProgressRead(**progress)


@router.post("/prompt-usage", response_model=PromptUsageResponse)
async def record_prompt_usage(
    data: PromptUsageRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Control group: record that user viewed a writing prompt.

    Returns current badge state and any newly earned badges.
    """
    r = await db.execute(select(OridSession).filter(OridSession.id == data.session_id))
    session = r.scalars().first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    week = data.week
    stage = (data.stage or "O").strip().upper()
    word_count = data.word_count

    # Count how many prompt views already exist for this session
    existing_stmt = select(func.coalesce(func.sum(OridBadgeEvent.prompt_view_count), 0)).where(
        OridBadgeEvent.user_id == user.id,
        OridBadgeEvent.session_id == session.id,
        OridBadgeEvent.week == week,
    )
    existing_count_res = await db.execute(existing_stmt)
    existing_prompt_views = int(existing_count_res.scalar() or 0)
    new_prompt_total = existing_prompt_views + data.prompt_view_count

    # Badge evaluation
    has_content = bool(word_count and word_count > 0)
    prev_badges = await get_earned_badges_from_db(db, user_id=user.id, session_id=session.id, week=week)
    current_badges = calculate_earned_badges(
        has_writing_content=has_content,
        has_used_feedback_or_prompt=True,
        total_score=None,
    )
    new_badges = get_new_badges(prev_badges, current_badges)
    if new_badges:
        await record_badge_events(
            db,
            user_id=user.id,
            session_id=session.id,
            reading_id=session.reading_id,
            week=week,
            task_type="orid_stage",
            condition=session.condition,
            new_badge_ids=new_badges,
            total_score=None,
            word_count=word_count,
            feedback_count=0,
            prompt_view_count=new_prompt_total,
            used_feedback_or_prompt=True,
        )
        await db.commit()

    all_earned = list(set(prev_badges + current_badges))
    return PromptUsageResponse(
        prompt_view_count=new_prompt_total,
        earnedBadges=all_earned,
        newlyEarnedBadges=new_badges,
    )


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

    stage_in = (data.stage or "O").strip().upper()
    draft_key = (data.draft or "d1").strip().lower()
    if draft_key not in ("d1", "d2"):
        draft_key = "d1"
    source = (data.source or "free_text").strip().lower()
    body = (data.student_text or "").strip()

    fb_rubric: dict[str, Any] = {}

    if source == "synthesis_feedback":
        if stage_in != "ALL":
            raise HTTPException(status_code=400, detail="synthesis_feedback requires stage ALL")
        stage_ctx = "ALL"
    else:
        stage_ctx = stage_in if stage_in in ("O", "R", "I", "D") else "O"

    if source == "feedback_button" and not body:
        raise HTTPException(status_code=400, detail="student_text is empty for feedback_button")

    if source == "synthesis_feedback" and not body:
        raise HTTPException(status_code=400, detail="student_text is empty")

    if source not in ("feedback_button", "synthesis_feedback") and not body:
        raise HTTPException(status_code=400, detail="student_text is empty")

    if body and _is_meta_or_injection_text(body):
        raise HTTPException(
            status_code=400,
            detail="這段內容看起來像是在要求系統忽略規則，請直接描述你的想法或作文內容。",
        )

    if body:
        unsafe, unsafe_reason = await check_safety(body, writing_coach=True)
        if unsafe:
            raise HTTPException(
                status_code=400,
                detail=f"這段內容目前不適合送出：{unsafe_reason}。請改成尊重、安全的說法後再試一次。",
            )

    input_bucket = classify_student_input(body) if body else classify_student_input("")
    draft_excerpt = truncate_student_draft_excerpt(body)

    if not await _allow_chat_message(db, user.id):
        msg = "請慢一點，我們一次說一個重點。"
        db.add(OridChatMessage(session_id=session.id, stage=stage_ctx, sender="ai", text=msg))
        await db.commit()
        return WritingCoachChatResponse(
            session_id=session.id,
            ai_reply=msg,
            stage=stage_ctx,
            meta={"rate_limited": True},
        )

    if source == "feedback_button":
        display_student = f"[{stage_ctx} {_draft_label_zh(draft_key)}]\n{body}"
    elif source == "synthesis_feedback":
        syn_tags = ["整合寫作"]
        sp = getattr(data, "synthesis_phase", None)
        if sp:
            syn_tags.append(str(sp).replace("_", " "))
        fr = int(getattr(data, "feedback_round", None) or 1)
        if fr != 1:
            syn_tags.append(f"第{fr}輪")
        display_student = f"[{'·'.join(syn_tags)}]\n{body}"
    else:
        display_student = body

    db.add(OridChatMessage(session_id=session.id, stage=stage_ctx, sender="student", text=display_student))
    await db.commit()

    msgs = await _load_recent_session_messages(
        db,
        session.id,
        limit=max(ORID_HISTORY_LIMIT + 12, 24),
    )

    coach_turn_seed = f"{user.id}:{session.id}:{len(msgs)}"
    opening_hint = pick_variant(coach_turn_seed, input_bucket)
    prev_ai_opener = _prev_ai_opener_from_messages(msgs)
    display_nm = (getattr(user, "display_name", None) or "").strip() or None
    login_id = (getattr(user, "email", None) or "").strip() or None

    condition = normalize_orid_condition(session.condition, default=DEFAULT_ORID_CONDITION)
    fb_ok: Optional[bool] = None
    fb_missing: list[str] = []
    fb_sug: list[str] = []
    fb_ex: Optional[str] = None
    fb_imp: Optional[str] = None
    fb_praise: Optional[str] = None
    coach_meta: dict[str, Any] = {}
    feedback_strength = detect_feedback_strength(stage_ctx, body) if source == "feedback_button" else None

    if source == "feedback_button":
        anchor_line = book_anchor_one_line(book_pack)
        fb_rubric: dict[str, Any] = {}
        genai_path = not is_control_condition(condition, default=DEFAULT_ORID_CONDITION)
        grounding_check: Optional[BookGroundingCheck] = None
        if (
            genai_path
            and client is not None
            and stage_ctx.strip().upper() in ("O", "R", "I")
            and not skip_book_grounding_enforcement(input_bucket, student_text=body, book_pack=book_pack)
        ):
            grounding_check = await _llm_book_grounding_check(
                student_text=body,
                stage=stage_ctx,
                book_pack=book_pack,
            )
        if not genai_path:
            fb_ok, fb_missing, fb_sug, fb_ex, fb_praise = _control_feedback(stage_ctx, body)
            fb_imp = None
            if (
                stage_ctx.strip().upper() == "O"
                and (anchor_line or "").strip()
                and is_o_placeholder_or_stuck_draft(body)
            ):
                fb_ex = None
        else:
            fb_ok, fb_missing, fb_sug, fb_ex, fb_imp, fb_praise, fb_rubric = await _genai_feedback(
                stage=stage_ctx,
                text=body,
                book_pack=book_pack,
                input_bucket=input_bucket,
                grounding_check=grounding_check,
            )

        fb_ok, fb_missing, fb_sug = await _enforce_feedback_book_grounding(
            body,
            book_pack,
            stage_ctx,
            bool(fb_ok),
            fb_missing,
            fb_sug,
            use_llm_checker=genai_path,
            input_bucket=input_bucket,
            grounding_check=grounding_check,
        )
        fb_missing, fb_sug = normalize_feedback_focus(
            stage=stage_ctx,
            missing=fb_missing,
            suggestions=fb_sug,
            student_text=body,
        )
        fb_missing, fb_sug = apply_o_key_event_gaps(
            stage=stage_ctx,
            strength=feedback_strength or "mid",
            student_text=body,
            key_events=(book_pack or {}).get("key_events"),
            missing=fb_missing,
            suggestions=fb_sug,
        )
        grounding_issue = _has_feedback_book_grounding_issue(fb_missing)
        if grounding_issue:
            fb_praise = _book_grounding_praise(stage_ctx)
            fb_ex = _book_grounding_example(stage_ctx, book_pack)

        fb_sug = scaffold_feedback_suggestions(stage_ctx, fb_sug)
        fb_ex = scaffold_feedback_example(stage_ctx, fb_ex)

        fb_ok = _apply_orid_rubric_ok_rule(bool(fb_ok), fb_rubric, fb_missing)

        if grounding_issue:
            ai_reply = format_control_feedback_reply(
                ok=bool(fb_ok),
                missing=fb_missing,
                suggestions=fb_sug,
                stage=stage_ctx,
                book_anchor=anchor_line,
                example=fb_ex,
                praise=fb_praise,
                student_draft=body,
            )
        elif is_control_condition(condition, default=DEFAULT_ORID_CONDITION) or client is None:
            ai_reply = format_control_feedback_reply(
                ok=bool(fb_ok),
                missing=fb_missing,
                suggestions=fb_sug,
                stage=stage_ctx,
                book_anchor=anchor_line,
                example=fb_ex,
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
                    "rubric_focus": fb_rubric.get("rubric_focus"),
                    "rubric_level_estimate": fb_rubric.get("rubric_level_estimate"),
                },
                ensure_ascii=False,
            )
            sys_n, user_n = build_feedback_narration_prompt(
                stage=stage_ctx,
                feedback_json_summary=summary,
                student_display_name=display_nm,
                student_login=login_id,
                student_draft_excerpt=draft_excerpt,
                input_bucket=input_bucket,
                opening_hint=opening_hint,
                prev_ai_opener=prev_ai_opener,
            )
            try:
                ai_reply = await _chat_completion(
                    [
                        {"role": "system", "content": sys_n},
                        {"role": "user", "content": user_n},
                    ],
                    max_completion_tokens=min(
                        ORID_FEEDBACK_NARRATION_MAX_COMPLETION_TOKENS,
                        int(OPENAI_MAX_COMPLETION_TOKENS or 2000),
                    ),
                    temperature=ORID_FOLLOWUP_TEMPERATURE,
                )
            except Exception:
                ai_reply = format_control_feedback_reply(
                    ok=bool(fb_ok),
                    missing=fb_missing,
                    suggestions=fb_sug,
                    stage=stage_ctx,
                    book_anchor=anchor_line,
                    example=fb_ex,
                    praise=fb_praise,
                    student_draft=body,
                )
            if not _looks_valid_feedback_narration(ai_reply):
                ai_reply = format_control_feedback_reply(
                    ok=bool(fb_ok),
                    missing=fb_missing,
                    suggestions=fb_sug,
                    stage=stage_ctx,
                    book_anchor=anchor_line,
                    example=fb_ex,
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
                    example=fb_ex,
                    praise=fb_praise,
                    student_draft=body,
                )

        await _try_dual_write_feedback(
            db,
            session_id=session.id,
            user_id=user.id,
            stage=stage_ctx,
            draft=draft_key,
            student_text=body,
            feedback_strength=feedback_strength,
            condition=condition,
            source=source,
            ok=bool(fb_ok),
            praise=fb_praise,
            missing=fb_missing,
            suggestions=fb_sug,
            example=fb_ex,
        )
        if fb_ok:
            await _maybe_advance_stage(db, session.id, stage_ctx)
    elif source == "synthesis_feedback":
        week1_raw = await _fetch_latest_writing_content_for_week(db, user.id, session.id, 1)
        week1_slots = _orid_stage_d1_from_writing_content(week1_raw)
        book_context = build_book_context_block(book_pack)
        syn_phase = getattr(data, "synthesis_phase", None)
        syn_round = int(getattr(data, "feedback_round", None) or 1)
        if syn_round not in (1, 2):
            syn_round = 1
        reading_ex = getattr(data, "reading_excerpt", None)
        syn_clarify = bool(getattr(data, "synthesis_clarify", False))
        sys_p = build_synthesis_coach_system_prompt(
            book_context=book_context,
            week1_orid_lines=week1_slots,
            student_display_name=display_nm,
            student_login=login_id,
            opening_hint=opening_hint,
            prev_ai_opener=prev_ai_opener,
            synthesis_phase=syn_phase,
            feedback_round=syn_round,
            reading_excerpt=reading_ex,
            synthesis_clarify=syn_clarify,
        )
        hist_syn: list[dict[str, str]] = []
        for m in msgs[-ORID_HISTORY_LIMIT:]:
            role = "user" if m.sender == "student" else "assistant"
            hist_syn.append({"role": role, "content": str(m.text or "")})
        oa_syn: list[dict[str, str]] = [{"role": "system", "content": sys_p}]
        oa_syn.extend(hist_syn)
        try:
            ai_reply = await _chat_completion(
                oa_syn,
                max_completion_tokens=OPENAI_MAX_COMPLETION_TOKENS,
                temperature=OPENAI_TEMPERATURE if OPENAI_TEMPERATURE is not None else ORID_MAIN_FALLBACK_TEMPERATURE,
            )
        except Exception:
            ai_reply = "我這邊有點忙不過來，你先儲存草稿，等一下再試試看。"
        if not (ai_reply or "").strip():
            ai_reply = "我有看到你的整合草稿，你可以再說一下最想調整的是銜接、具體例子，還是心得的深度？"
        coach_meta["synthesis_context"] = True
        coach_meta["synthesis_phase"] = syn_phase
        coach_meta["feedback_round"] = syn_round
        if reading_ex:
            coach_meta["reading_excerpt_injected"] = True
    else:
        if is_control_condition(condition, default=DEFAULT_ORID_CONDITION):
            ai_reply = format_control_free_text_reply(stage_ctx)
        else:
            book_context = build_book_context_block(book_pack)
            sys_p = build_writing_coach_system_prompt(
                stage=stage_ctx,
                book_context=book_context,
                source=source,
                student_display_name=display_nm,
                student_login=login_id,
                input_bucket=input_bucket,
                opening_hint=opening_hint,
                prev_ai_opener=prev_ai_opener,
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

    ai_reply = strip_markdown_for_student_chat((ai_reply or "").strip())

    db.add(OridChatMessage(session_id=session.id, stage=stage_ctx, sender="ai", text=ai_reply))
    await db.commit()

    logger.info(
        "writing_coach_chat completed",
        extra={
            "session_id": str(session.id),
            "stage": stage_ctx,
            "source": source,
            "condition": condition,
        },
    )

    # ---- Scoring + badge computation ----
    score_result: dict[str, Any] = {}
    badge_meta: dict[str, Any] = {}
    if source == "feedback_button":
        week_num = getattr(session, "book_unit", None)
        try:
            week_num = int(week_num or 1)
        except (ValueError, TypeError):
            week_num = 1

        orid_levels: dict[str, Any] = {}
        sel_levels: dict[str, Any] = {}
        try:
            saved_raw = await _fetch_latest_writing_content_for_week(
                db, user.id, session.id, week_num
            )
            if saved_raw:
                saved_obj = ensure_orid_writing_obj(
                    raw_content=saved_raw,
                    week=week_num,
                    empty_factory=_ensure_orid_writing_v1,
                )
                orid_levels, sel_levels = collect_levels_from_writing_obj(saved_obj)
        except Exception:
            logger.warning("collect saved rubric levels failed", exc_info=True)

        rubric_level_estimate = (fb_rubric or {}).get("rubric_level_estimate")
        rubric_focus = (fb_rubric or {}).get("rubric_focus")
        if rubric_level_estimate is not None and str(rubric_level_estimate).strip():
            apply_single_level_estimate(
                stage=stage_ctx,
                rubric_focus=rubric_focus,
                rubric_level_estimate=rubric_level_estimate,
                orid_levels=orid_levels,
                sel_levels=sel_levels,
            )
            score_result = calculate_orid_sel_score(orid_levels, sel_levels)

        # Badge evaluation — always run after feedback, even without rubric data
        has_content = bool((body or "").strip())
        total_score_int = score_result.get("totalScore") if score_result else None
        prev_badges = await get_earned_badges_from_db(db, user_id=user.id, session_id=session.id, week=week_num)
        current_badges = calculate_earned_badges(
            has_writing_content=has_content,
            has_used_feedback_or_prompt=True,
            total_score=total_score_int,
        )
        new_badges = get_new_badges(prev_badges, current_badges)
        try:
            if new_badges:
                await record_badge_events(
                    db,
                    user_id=user.id,
                    session_id=session.id,
                    reading_id=session.reading_id,
                    week=week_num,
                    task_type="orid_stage",
                    condition=condition,
                    new_badge_ids=new_badges,
                    total_score=total_score_int,
                    word_count=len(body) if body else 0,
                    feedback_count=1,
                    prompt_view_count=0,
                    used_feedback_or_prompt=True,
                )
            if total_score_int is not None:
                await update_session_score_snapshot(
                    db,
                    user_id=user.id,
                    session_id=session.id,
                    week=week_num,
                    total_score=total_score_int,
                )
            if new_badges or total_score_int is not None:
                await db.commit()
        except Exception:
            logger.exception(
                "badge/score persistence failed",
                extra={"session_id": str(session.id)},
            )
        badge_meta = {
            "earnedBadges": list(set(prev_badges + current_badges)),
            "newlyEarnedBadges": new_badges,
        }

    coach_meta.update(
        {
            "condition": condition,
            "source": source,
            "draft": draft_key,
            "feedback_strength": feedback_strength,
            "input_bucket": input_bucket,
            "opening_hint": opening_hint,
            **({"rubric_focus": rf} if (rf := (fb_rubric.get("rubric_focus") if source == "feedback_button" else None)) else {}),
            **({"rubric_level_estimate": rl} if (rl := (fb_rubric.get("rubric_level_estimate") if source == "feedback_button" else None)) else {}),
            **({"score": score_result} if score_result else {}),
            **badge_meta,
        }
    )
    return WritingCoachChatResponse(
        session_id=session.id,
        ai_reply=ai_reply,
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

    msgs = await _load_recent_session_messages(db, session.id, limit=24)

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
    feedback_strength = detect_feedback_strength(data.stage, text)
    wf_input_bucket = classify_student_input(text)

    praise: Optional[str] = None
    rubric_snap: dict[str, Any] = {}
    genai_path = not is_control_condition(condition, default=DEFAULT_ORID_CONDITION)
    grounding_check: Optional[BookGroundingCheck] = None
    if (
        genai_path
        and client is not None
        and (data.stage or "O").strip().upper() in ("O", "R", "I")
        and not skip_book_grounding_enforcement(wf_input_bucket, student_text=text, book_pack=book_pack)
    ):
        grounding_check = await _llm_book_grounding_check(
            student_text=text,
            stage=data.stage,
            book_pack=book_pack,
        )
    if not genai_path:
        ok, missing, suggestions, _, praise = _control_feedback(data.stage, text)
        example = None
        improved = None
    else:
        ok, missing, suggestions, example, improved, praise, rubric_snap = await _genai_feedback(
            stage=data.stage,
            text=text,
            book_pack=book_pack,
            input_bucket=wf_input_bucket,
            grounding_check=grounding_check,
        )

    ok, missing, suggestions = await _enforce_feedback_book_grounding(
        text,
        book_pack,
        data.stage,
        bool(ok),
        missing,
        suggestions,
        use_llm_checker=genai_path,
        input_bucket=wf_input_bucket,
        grounding_check=grounding_check,
    )
    missing, suggestions = normalize_feedback_focus(
        stage=data.stage,
        missing=missing,
        suggestions=suggestions,
        student_text=text,
    )
    missing, suggestions = apply_o_key_event_gaps(
        stage=data.stage,
        strength=feedback_strength,
        student_text=text,
        key_events=(book_pack or {}).get("key_events"),
        missing=missing,
        suggestions=suggestions,
    )
    if _has_feedback_book_grounding_issue(missing):
        praise = _book_grounding_praise(data.stage)

    ok = _apply_orid_rubric_ok_rule(bool(ok), rubric_snap, missing)

    await _try_dual_write_feedback(
        db,
        session_id=session.id,
        user_id=user.id,
        stage=data.stage,
        draft=data.draft,
        student_text=text,
        feedback_strength=feedback_strength,
        condition=condition,
        source="writing_feedback_api",
        ok=ok,
        praise=praise,
        missing=missing,
        suggestions=suggestions,
        example=example,
    )
    if ok:
        await _maybe_advance_stage(db, session.id, data.stage)

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
            "feedback_strength": feedback_strength,
            **rubric_snap,
            "model": OPENAI_MODEL,
            "max_completion_tokens": OPENAI_MAX_COMPLETION_TOKENS,
            "saved_to_writing_id": None,
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

    content_str = data.content.strip()
    ins = pg_insert(OridWeekSubmission).values(
        id=uuid4(),
        user_id=user.id,
        reading_id=data.reading_id,
        session_id=data.session_id,
        week=data.week,
        content=content_str,
    )
    ins = ins.on_conflict_do_update(
        constraint="uq_orid_week_submissions_user_session_week",
        set_={
            "content": ins.excluded.content,
            "reading_id": ins.excluded.reading_id,
            "updated_at": func.now(),
        },
    ).returning(OridWeekSubmission)

    res = await db.execute(ins)
    w = res.scalar_one()
    await db.commit()
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
    q = select(OridWeekSubmission).filter(OridWeekSubmission.user_id == user.id)

    if session_id:
        q = q.filter(OridWeekSubmission.session_id == session_id)
    if reading_id:
        q = q.filter(OridWeekSubmission.reading_id == reading_id)
    if week:
        q = q.filter(OridWeekSubmission.week == week)

    q = q.order_by(OridWeekSubmission.created_at.desc())
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
        select(OridWeekSubmission).filter(
            OridWeekSubmission.id == writing_id,
            OridWeekSubmission.user_id == user.id,
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

    reading = None
    if session.reading_id:
        r_reading = await db.execute(select(Reading).filter(Reading.id == session.reading_id))
        reading = r_reading.scalars().first()
    await seed_writing_coach_welcome_if_needed(db, session=session, reading=reading)

    q = select(OridChatMessage).filter(OridChatMessage.session_id == session_id)
    q = q.order_by(OridChatMessage.created_at.asc() if order == "asc" else OridChatMessage.created_at.desc())
    q = q.limit(limit)

    res = await db.execute(q)
    return res.scalars().all()
