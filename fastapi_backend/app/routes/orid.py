from uuid import UUID
from typing import Optional
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from openai import AsyncOpenAI

from app.database import get_async_session, User
from app.users import current_active_user
from app.models import Reading, OridSession, OridMessage, OridWriting
from app.schemas import (
    ReadingCreate, ReadingRead,
    OridSessionCreate, OridSessionRead,
    OridChatRequest, OridChatResponse,
    OridWritingCreate, OridWritingUpdate, OridWritingRead,
)


router = APIRouter(tags=["orid"])

# ----------------------------
# OpenAI settings (from env)
# ----------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set in environment variables.")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ----------------------------
# ORID stage helpers
# ----------------------------
STAGE_ORDER = ["O", "R", "I", "D"]

def next_stage(stage: str) -> str:
    if stage not in STAGE_ORDER:
        return "O"
    idx = STAGE_ORDER.index(stage)
    return STAGE_ORDER[min(idx + 1, len(STAGE_ORDER) - 1)]

def ai_prompt_by_stage(stage: str) -> str:
    if stage == "O":
        return "請用 1–2 句話客觀描述故事發生了什麼？（不要加入感想）"
    if stage == "R":
        return "你讀到這裡的感受是什麼？可以選一個情緒詞並說原因。"
    if stage == "I":
        return "你覺得這件事最重要的意義/價值是什麼？為什麼？"
    return "如果下次遇到類似情境，你會怎麼做？可以提出一個具體行動。"

# ----------------------------
# PASS-tag parsing (like your old system)
# ----------------------------
PASS_RE = re.compile(r"【PASS:(true|false)】", re.IGNORECASE)
NEXT_RE = re.compile(r"【NEXT:([ORID])】", re.IGNORECASE)
REASON_RE = re.compile(r"【REASON:(.*?)】")

def parse_control_tags(text: str):
    """
    期待 LLM 回覆格式（第一行/開頭帶標籤）：
      【PASS:true】【NEXT:R】【REASON:...】
      <給學生看的正常文字...>

    回傳：
      pass_ok: bool
      next_stage_suggested: Optional[str]
      reason: Optional[str]
      clean_text: str (去掉標籤後)
    """
    pass_ok = False
    next_s = None
    reason = None

    m = PASS_RE.search(text)
    if m:
        pass_ok = (m.group(1).lower() == "true")

    m2 = NEXT_RE.search(text)
    if m2:
        next_s = m2.group(1).upper()

    m3 = REASON_RE.search(text)
    if m3:
        reason = m3.group(1).strip()

    # 去掉所有控制標籤
    clean = PASS_RE.sub("", text)
    clean = NEXT_RE.sub("", clean)
    clean = REASON_RE.sub("", clean)
    clean = clean.strip()

    return pass_ok, next_s, reason, clean

async def llm_generate_reply(stage: str, history: list[dict]) -> str:
    """
    history 格式：[{ "role": "user"/"assistant", "content": "..." }, ...]
    這裡讓 LLM 同時做兩件事：
      1) 判定學生最新回答在此階段是否「合格」→ PASS
      2) 給一段友善、簡短、下一步追問
    """
    # 你要的「像舊系統」：用標籤讓後端可解析
    system_prompt = f"""
你是一位給台灣國小學生使用的「閱讀反思學習同伴」。
你要依 ORID 四階段引導學生思考：O(客觀)→R(感受)→I(意義)→D(行動)。
目前階段：{stage}

你必須在回覆最開頭輸出控制標籤（讓系統解析）：
- 【PASS:true】或【PASS:false】 代表「學生剛剛那句回答」是否符合本階段要求
- 【NEXT:X】 X 只能是 O/R/I/D，代表你建議下一階段（通常是下一個階段）
- 【REASON:...】 若 PASS=false，請用很短的中文說原因（例如：太短/沒提到感受/沒有原因/不夠具體）

然後在標籤後面，才輸出「給學生看的文字」（友善、短句、一次只問 1 個問題）。

本階段合格判定（請嚴格一些，避免亂答就過）：
- O：必須描述事情發生了什麼（事件/角色/情節），不要只給單字/符號；不要只講感受
- R：必須出現感受/情緒，且有原因（例如：因為…所以…）
- I：必須說出意義/價值/學到什麼，且有理由
- D：必須提出一個具體可做的行動（下次我會…），不能太空泛

回覆規則：
- 一律繁體中文
- 不要說你是 AI 模型，不要提 OpenAI
- 不要輸出任何多餘括號或 JSON，只要標籤 + 正常文字
""".strip()

    stage_hint = ai_prompt_by_stage(stage)

    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"本階段引導方向：{stage_hint}"},
            *history,
        ],
    )

    return resp.choices[0].message.content.strip()

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
        stage_turn=0,  # ✅ 這裡改成「本階段合格次數」計數器
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s

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

    stage = session.current_stage

    # 1) 存學生訊息
    db.add(
        OridMessage(
            session_id=session.id,
            stage=stage,
            sender="student",
            text=data.student_text,
        )
    )
    await db.commit()

    # 2) 讀取對話紀錄（最多 12 則）→ LLM history
    q = await db.execute(
        select(OridMessage)
        .filter(OridMessage.session_id == session.id)
        .order_by(OridMessage.created_at.asc())
    )
    msgs = q.scalars().all()

    history = []
    for m in msgs[-12:]:
        role = "user" if m.sender == "student" else "assistant"
        history.append({"role": role, "content": m.text})

    # 3) 呼叫 LLM（回覆含 PASS 標籤）
    raw_ai = await llm_generate_reply(stage, history)

    pass_ok, next_suggest, reason, clean_ai = parse_control_tags(raw_ai)

    # 4) 存 AI 訊息（✅ 先存「乾淨文字」，不要把標籤顯示給學生）
    db.add(
        OridMessage(
            session_id=session.id,
            stage=stage,
            sender="ai",
            text=clean_ai,
        )
    )

    # 5) ✅ 改成「合格才累加」，不合格不加
    if pass_ok:
        session.stage_turn += 1

    # 6) ✅ 達標才跳階（你先用 2 次合格；之後可按階段不同調整）
    REQUIRED_PASS = 2
    if stage == "D":
        REQUIRED_PASS = 1

    if session.stage_turn >= REQUIRED_PASS and session.current_stage != "D":
        # 防止跳太多：只允許往下一階
        session.current_stage = next_stage(session.current_stage)
        session.stage_turn = 0

    await db.commit()
    await db.refresh(session)

    # 回傳：前端可以用 pass/reason 顯示「這句不合格」提示
    return OridChatResponse(
        session_id=session.id,
        stage=stage,
        ai_reply=clean_ai,
        current_stage=session.current_stage,
        stage_turn=session.stage_turn,
        pass_ok=pass_ok,
        reason=reason if (not pass_ok) else None,
        next_suggested=next_suggest,
    )

@router.post("/writings", response_model=OridWritingRead)
async def create_writing(
    data: OridWritingCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    # 1) session 必須存在且屬於本人
    r = await db.execute(select(OridSession).filter(OridSession.id == data.session_id))
    session = r.scalars().first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2) reading 必須存在（順便檢查 reading_id 是否一致）
    rr = await db.execute(select(Reading).filter(Reading.id == data.reading_id))
    reading = rr.scalars().first()
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")

    if session.reading_id != data.reading_id:
        raise HTTPException(status_code=400, detail="reading_id does not match session.reading_id")

    # 3) week 基本檢查
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
    # 找到該 writing（且必須是本人）
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