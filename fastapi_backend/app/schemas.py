import uuid
from datetime import datetime
from uuid import UUID

from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict


# ----------------------------
# Users (fastapi-users)
# ----------------------------
class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


# ----------------------------
# Items (example)
# ----------------------------
class ItemBase(BaseModel):
    name: str
    description: str | None = None
    quantity: int | None = None


class ItemCreate(ItemBase):
    pass


class ItemRead(ItemBase):
    id: UUID
    user_id: UUID

    model_config = ConfigDict(from_attributes=True)


# ----------------------------
# Readings
# ----------------------------
class ReadingCreate(BaseModel):
    title: str
    content: str


class ReadingRead(ReadingCreate):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ----------------------------
# ORID Sessions
# ----------------------------
class OridSessionCreate(BaseModel):
    reading_id: UUID
    condition: str | None = None


class OridSessionRead(BaseModel):
    id: UUID
    reading_id: UUID
    condition: str | None
    current_stage: str
    stage_turn: int

    # ✅ OpenAI Assistants thread id（每個 session 綁一個 thread）
    thread_id: str | None = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ----------------------------
# ORID Chat
# ----------------------------
class OridChatRequest(BaseModel):
    session_id: UUID
    student_text: str


class OridChatResponse(BaseModel):
    session_id: UUID
    # 你現在可能回 stage + current_stage 都有，先保留避免前端壞掉
    stage: str
    ai_reply: str
    current_stage: str
    stage_turn: int

    # ✅ 讓 orid.py 可回傳（避免 500）
    pass_ok: bool | None = None
    reason: str | None = None
    next_suggested: str | None = None



# ----------------------------
# ORID Writings
# ----------------------------
class OridWritingCreate(BaseModel):
    reading_id: UUID
    session_id: UUID
    week: int
    content: str


# ✅ 更新 writing 用（PUT）
class OridWritingUpdate(BaseModel):
    content: str


class OridWritingRead(BaseModel):
    id: UUID
    user_id: UUID
    reading_id: UUID
    session_id: UUID
    week: int
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ----------------------------
# ORID Messages (chat logs)
# ----------------------------
class OridMessageRead(BaseModel):
    id: UUID
    session_id: UUID
    stage: str
    sender: str
    text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
