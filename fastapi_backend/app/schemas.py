import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict, Field


# ----------------------------
# Users (fastapi-users)
# ----------------------------
class UserRead(schemas.BaseUser[uuid.UUID]):
    role: str = "student"


class UserCreate(schemas.BaseUserCreate):
    role: str = "student"


class UserUpdate(schemas.BaseUserUpdate):
    role: str | None = None


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


class WritingCoachChatRequest(BaseModel):
    session_id: UUID
    student_text: str
    stage: str = Field(..., pattern="^(O|R|I|D)$")
    draft: str = Field("d1", pattern="^(d1|d2)$")
    source: str = Field(..., pattern="^(free_text|feedback_button)$")
    week: int = Field(1, ge=1, le=6)
    save_feedback: bool = True


class WritingCoachChatResponse(BaseModel):
    session_id: UUID
    ai_reply: str
    stage: str
    feedback_ok: bool | None = None
    feedback_praise: str | None = None
    feedback_missing: list[str] = []
    feedback_suggestions: list[str] = []
    feedback_example: str | None = None
    feedback_improved: str | None = None
    meta: dict[str, Any] = {}


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


class TeacherClassRead(BaseModel):
    id: UUID
    name: str
    year: int
    external_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TeacherStudentRow(BaseModel):
    student_id: UUID
    student_email: str
    current_stage: str
    interaction_count: int
    writing_completed_stages: int
    last_activity_at: datetime | None = None
    # analytics extras (None when analytics tables have no data yet)
    feedback_click_count: int = 0
    feedback_ok_count: int = 0
    feedback_ok_stages: int = 0   # # of stages with ≥1 ok=true event


class TeacherClassOverview(BaseModel):
    class_id: UUID
    class_name: str
    week: int
    total_students: int
    active_students: int
    completion_rate: float            # has-text definition (unchanged)
    feedback_ok_rate: float = 0.0    # fraction of students with all 4 stages ok
    stage_distribution: dict[str, int]
    students: list[TeacherStudentRow]


class TeacherStudentSummary(BaseModel):
    class_id: UUID
    student_id: UUID
    student_email: str
    week: int
    current_stage: str
    interaction_count: int
    writing_completed_stages: int
    stages_with_draft: list[str] = []
    last_activity_at: datetime | None = None
    feedback_click_count: int = 0
    feedback_ok_count: int = 0
    feedback_ok_stages: int = 0


class PostTestScoreUpsert(BaseModel):
    week: int
    stage: str          # O / R / I / D / ALL
    score: int
    max_score: int = 3
    rubric_id: str | None = None
    note: str | None = None


class PostTestScoreRead(BaseModel):
    id: UUID
    student_id: UUID
    grader_id: UUID
    class_id: UUID
    week: int
    stage: str
    rubric_id: str | None = None
    score: int
    max_score: int
    note: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
