import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


def json_dt_utc_z(dt: datetime | None) -> str | None:
    """將 DB 常見的 naive UTC（或已帶時區）轉成 ISO 字串並附 Z，避免前端把無時區字串誤當本地時間。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


# ----------------------------
# Users (fastapi-users)
# ----------------------------
class UserRead(schemas.BaseUser[uuid.UUID]):
    """email 欄位實際為登入帳號（學號等），非必為 email 格式。"""
    email: str  # type: ignore[assignment]
    role: str = "student"
    display_name: str | None = None


class UserCreate(schemas.BaseUserCreate):
    """登入帳號存於 API/DB 的 email 欄位；可為學號。"""
    email: str = Field(..., min_length=1, max_length=128)
    display_name: str | None = Field(None, max_length=128)
    role: str = "student"

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("Account (login id) is required")
        return s

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None


class UserUpdate(schemas.BaseUserUpdate):
    email: str | None = Field(None, max_length=128)  # type: ignore[assignment]
    role: str | None = None
    display_name: str | None = Field(None, max_length=128)

    @field_validator("email")
    @classmethod
    def strip_email_optional(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None


class OridMeCapabilitiesRead(BaseModel):
    """與後端 ORID_FORCE_NEW_ALLOWLIST 一致，供前端決定是否顯示強制開新 session。"""

    orid_can_force_new: bool


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
    book_unit: int | None = None

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
    stage: str = Field(..., pattern="^(O|R|I|D|ALL)$")
    draft: str = Field("d1", pattern="^(d1|d2)$")
    source: str = Field(..., pattern="^(free_text|feedback_button|synthesis_feedback)$")
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
    updated_at: datetime

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

    @field_serializer("created_at")
    def _ser_orid_msg_created_at(self, v: datetime) -> str:
        return json_dt_utc_z(v) or ""


class TeacherClassRead(BaseModel):
    id: UUID
    name: str
    year: int
    external_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TeacherStudentRow(BaseModel):
    student_id: UUID
    student_email: str
    student_display_name: str
    current_stage: str
    interaction_count: int = Field(
        description="對話輪數：該週 session 內 min(學生訊息則數, AI 訊息則數)。",
    )
    writing_completed_stages: int
    last_activity_at: datetime | None = None
    # analytics extras (None when analytics tables have no data yet)
    feedback_click_count: int = 0
    feedback_ok_count: int = 0
    feedback_ok_stages: int = 0   # # of stages with ≥1 ok=true event

    @field_serializer("last_activity_at")
    def _ser_last_activity_at_row(self, v: datetime | None) -> str | None:
        return json_dt_utc_z(v)


class TeacherClassOverview(BaseModel):
    class_id: UUID
    class_name: str
    week: int
    total_students: int
    active_students: int
    completion_rate: float            # has-text definition (unchanged)
    feedback_ok_rate: float = 0.0    # fraction of students with all 4 stages ok
    # keys NOT_STARTED,O,R,I,D — O～D 為「至少有寫該段」的人數（可與總人數重疊加總）；
    # NOT_STARTED 為四段皆無寫作者人數。
    stage_distribution: dict[str, int]
    students: list[TeacherStudentRow]


class TeacherStudentSummary(BaseModel):
    class_id: UUID
    student_id: UUID
    student_email: str
    student_display_name: str
    week: int
    current_stage: str
    interaction_count: int = Field(
        description="對話輪數：該週 session 內 min(學生訊息則數, AI 訊息則數)。",
    )
    writing_completed_stages: int
    stages_with_draft: list[str] = []
    last_activity_at: datetime | None = None
    feedback_click_count: int = 0
    feedback_ok_count: int = 0
    feedback_ok_stages: int = 0

    @field_serializer("last_activity_at")
    def _ser_last_activity_at_summary(self, v: datetime | None) -> str | None:
        return json_dt_utc_z(v)


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
