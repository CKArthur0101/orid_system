from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import uuid

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
    orid_condition: str = "experimental"


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
# Admin (user / class management)
# ----------------------------
ADMIN_ASSIGNABLE_ROLES = frozenset({"student", "teacher"})
ADMIN_ASSIGNABLE_CONDITIONS = frozenset({"experimental", "control"})


class AdminClassSummary(BaseModel):
    id: UUID
    name: str
    year: int
    external_code: str | None = None
    student_count: int = 0
    teacher_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AdminClassCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    year: int = Field(default_factory=lambda: datetime.now().year)
    external_code: str | None = Field(None, max_length=64)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("Class name is required")
        return s

    @field_validator("external_code")
    @classmethod
    def strip_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None


class AdminClassUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    year: int | None = None
    external_code: str | None = Field(None, max_length=64)


class AdminUserListItem(BaseModel):
    id: UUID
    email: str
    display_name: str | None = None
    role: str
    is_active: bool
    orid_condition: str = "experimental"
    class_names: list[str] = Field(default_factory=list)
    class_ids: list[UUID] = Field(default_factory=list)


class AdminUserDetail(AdminUserListItem):
    is_verified: bool
    is_superuser: bool


class AdminUserCreate(BaseModel):
    email: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=128)
    display_name: str | None = Field(None, max_length=128)
    role: str = "student"
    orid_condition: str = "experimental"
    class_ids: list[UUID] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("Account is required")
        return s

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @field_validator("role")
    @classmethod
    def normalize_role(cls, v: str) -> str:
        r = (v or "student").strip().lower()
        if r not in ADMIN_ASSIGNABLE_ROLES:
            raise ValueError("role must be student or teacher")
        return r

    @field_validator("orid_condition")
    @classmethod
    def normalize_orid_condition(cls, v: str) -> str:
        c = (v or "experimental").strip().lower()
        if c not in ADMIN_ASSIGNABLE_CONDITIONS:
            raise ValueError("orid_condition must be experimental or control")
        return c


class AdminUserUpdate(BaseModel):
    email: str | None = Field(None, max_length=128)
    display_name: str | None = Field(None, max_length=128)
    role: str | None = None
    orid_condition: str | None = None
    is_active: bool | None = None
    new_password: str | None = Field(None, min_length=1, max_length=128)
    class_ids: list[UUID] | None = None

    @field_validator("email")
    @classmethod
    def strip_email_optional(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @field_validator("role")
    @classmethod
    def normalize_role(cls, v: str | None) -> str | None:
        if v is None:
            return None
        r = v.strip().lower()
        if r not in ADMIN_ASSIGNABLE_ROLES:
            raise ValueError("role must be student or teacher")
        return r

    @field_validator("orid_condition")
    @classmethod
    def normalize_orid_condition(cls, v: str | None) -> str | None:
        if v is None:
            return None
        c = v.strip().lower()
        if c not in ADMIN_ASSIGNABLE_CONDITIONS:
            raise ValueError("orid_condition must be experimental or control")
        return c


class AdminUserCreateResponse(BaseModel):
    user: AdminUserDetail
    password_once: str


class AdminUserUpdateResponse(BaseModel):
    user: AdminUserDetail
    password_once: str | None = None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    total: int
    page: int
    page_size: int


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
    # Week-2 synthesis_feedback only (optional; omitted = legacy behavior)
    synthesis_phase: str | None = None
    feedback_round: int = Field(1, ge=1, le=2)
    reading_excerpt: str | None = Field(None, max_length=4000)
    synthesis_clarify: bool = False

    @field_validator("synthesis_phase", mode="before")
    @classmethod
    def _normalize_synthesis_phase(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        if not s:
            return None
        allowed = {"select_evidence", "align_prompt", "short_draft", "expand_revise"}
        return s if s in allowed else None

    @field_validator("reading_excerpt", mode="before")
    @classmethod
    def _strip_reading_excerpt(cls, v: Any) -> str | None:
        if v is None:
            return None
        t = str(v).strip()
        return t or None


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
# Control group prompt usage
# ----------------------------
class PromptUsageRequest(BaseModel):
    session_id: UUID
    week: int
    stage: str
    word_count: int | None = None
    prompt_view_count: int = 1  # How many additional views to count in this call


class PromptUsageResponse(BaseModel):
    prompt_view_count: int
    earnedBadges: list[str] = []
    newlyEarnedBadges: list[str] = []


class OridProgressRead(BaseModel):
    earnedBadges: list[str] = []
    totalScore: int | None = None
    score: dict[str, Any] = {}


# ----------------------------
# ORID Writings
# ----------------------------
class OridWritingCreate(BaseModel):
    reading_id: UUID
    session_id: UUID
    week: int
    content: str
    # "submit" only when the student explicitly submits ("提交我的寫作");
    # omitted/"draft" covers autosave and the "儲存草稿" button — matches
    # existing behavior where drafts and submissions share the same upsert.
    save_intent: str = Field("draft", pattern="^(draft|submit)$")


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


# ----------------------------
# Teacher research dashboard (ORID Teacher Research MVP)
# ----------------------------
class ResearchSummaryCards(BaseModel):
    total_students: int
    experimental_count: int
    control_count: int
    submitted_count: int
    submission_rate: float
    avg_guide_use_count: float
    avg_total_score: float | None = None


class ResearchGroupComparisonRow(BaseModel):
    condition: str  # experimental / control
    student_count: int
    avg_word_count: float
    avg_save_count: float = 0.0
    avg_revision_count: float
    avg_guide_use_count: float
    avg_badge_count: float
    avg_orid_score: float | None = None
    avg_sel_score: float | None = None
    avg_total_score: float | None = None
    submission_rate: float


class ResearchWeeklyTrendPoint(BaseModel):
    week: int
    condition: str
    avg_word_count: float
    avg_save_count: float = 0.0
    avg_revision_count: float
    avg_guide_use_count: float
    avg_badge_count: float
    avg_orid_score: float | None = None
    avg_sel_score: float | None = None
    avg_total_score: float | None = None
    student_count: int


class ResearchCompletionDistribution(BaseModel):
    submitted: int
    not_submitted: int


class ResearchStudentRow(BaseModel):
    student_id: UUID
    student_email: str
    student_display_name: str
    condition: str
    week: int
    task_type: str | None = None
    word_count: int
    save_count: int
    revision_count: int
    guide_use_count: int
    badge_count: int
    orid_score: float | None = None
    sel_score: float | None = None
    total_score: int | None = None
    is_submitted: bool


class TeacherResearchOverview(BaseModel):
    class_id: UUID
    class_name: str
    week: int | None = None  # None = aggregated across weeks 1–6
    summary_cards: ResearchSummaryCards
    group_comparison: list[ResearchGroupComparisonRow]
    weekly_trends: list[ResearchWeeklyTrendPoint]
    completion_distribution: ResearchCompletionDistribution
    student_rows: list[ResearchStudentRow]
