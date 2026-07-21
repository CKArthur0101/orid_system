import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Text, func, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    role = Column(String, nullable=False, default="student", server_default="student")
    display_name = Column(String(128), nullable=True)
    # experimental / control; defaults to experimental to preserve existing AI sessions
    orid_condition = Column(String(16), nullable=False, default="experimental", server_default="experimental")
    orid_condition_updated_at = Column(DateTime(timezone=True), nullable=True)
    items = relationship("Item", back_populates="user", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    quantity = Column(Integer, nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)

    user = relationship("User", back_populates="items")


class Reading(Base):
    __tablename__ = "readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OridSession(Base):
    __tablename__ = "orid_sessions"
    __table_args__ = (
        Index("ix_orid_sessions_user_book_unit_created_at", "user_id", "book_unit", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    reading_id = Column(UUID(as_uuid=True), ForeignKey("readings.id"), nullable=False)

    # ✅ OpenAI Assistants thread id（每個 session 綁一個 thread）
    thread_id = Column(String, nullable=True, index=True)

    condition = Column(String, nullable=True)  # A/B 或 experimental/control
    current_stage = Column(String, default="O", nullable=False)  # O/R/I/D
    stage_turn = Column(Integer, default=0, nullable=False)      # 用來控制幾輪後進下一階段

    # 書單元 1–3：週 1–2→1、3–4→2、5–6→3；同單元共用一個 session 以延續聊天
    book_unit = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
    reading = relationship("Reading")
    messages = relationship("OridChatMessage", back_populates="session", cascade="all, delete-orphan")


class OridChatMessage(Base):
    __tablename__ = "orid_chat_messages"
    __table_args__ = (
        Index("ix_orid_chat_messages_session_created_at", "session_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("orid_sessions.id"), nullable=False, index=True)

    stage = Column(String, nullable=False)    # O/R/I/D
    sender = Column(String, nullable=False)   # "student" / "ai"
    text = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("OridSession", back_populates="messages")


class OridWeekSubmission(Base):
    """Official submitted ORID JSON per user/session/week; re-submit overwrites the same PK row."""

    __tablename__ = "orid_week_submissions"
    __table_args__ = (
        UniqueConstraint("user_id", "session_id", "week", name="uq_orid_week_submissions_user_session_week"),
        Index("ix_orid_week_submissions_user_week_session", "user_id", "week", "session_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    reading_id = Column(UUID(as_uuid=True), ForeignKey("readings.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("orid_sessions.id"), nullable=False)

    week = Column(Integer, nullable=False)  # 第幾週(1~6)
    content = Column(Text, nullable=False)  # 寫作 JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ClassRoom(Base):
    __tablename__ = "classes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    year = Column(Integer, nullable=False, default=datetime.utcnow().year)
    external_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StudentClassMembership(Base):
    __tablename__ = "student_class_memberships"
    __table_args__ = (
        UniqueConstraint("student_id", "class_id", name="uq_student_class_membership"),
        Index("ix_student_class_memberships_class_student", "class_id", "student_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TeacherClassAssignment(Base):
    __tablename__ = "teacher_class_assignments"
    __table_args__ = (UniqueConstraint("teacher_id", "class_id", name="uq_teacher_class_assignment"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OridStageAttempt(Base):
    """One row per feedback-button press: the student's draft snapshot."""

    __tablename__ = "orid_stage_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("orid_sessions.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)

    stage = Column(String(1), nullable=False)       # O / R / I / D
    draft = Column(String(4), nullable=False)        # d1 / d2
    student_text = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=False, default=0)
    feedback_strength = Column(String(8), nullable=True)  # low / mid / high
    condition = Column(String(32), nullable=True)    # genai / control
    source = Column(String(32), nullable=True)       # feedback_button / writing_feedback_api

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    feedback_events = relationship("OridFeedbackEvent", back_populates="attempt", cascade="all, delete-orphan")


class OridFeedbackEvent(Base):
    """One row per feedback result linked to an attempt."""

    __tablename__ = "orid_feedback_events"
    __table_args__ = (
        Index("ix_orid_feedback_events_session_stage_created_at", "session_id", "stage", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("orid_stage_attempts.id"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("orid_sessions.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)

    stage = Column(String(1), nullable=False)
    draft = Column(String(4), nullable=False)
    ok = Column(Boolean, nullable=False, default=False)
    praise = Column(Text, nullable=True)
    missing_json = Column(Text, nullable=True)       # JSON array string
    suggestions_json = Column(Text, nullable=True)   # JSON array string
    example = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    attempt = relationship("OridStageAttempt", back_populates="feedback_events")


class OridPostTestScore(Base):
    """Teacher-entered post-test rubric scores per student per stage per week."""

    __tablename__ = "orid_post_test_scores"
    __table_args__ = (
        UniqueConstraint("student_id", "week", "stage", name="uq_post_test_student_week_stage"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    grader_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)

    week = Column(Integer, nullable=False)
    stage = Column(String(4), nullable=False)   # O / R / I / D / ALL
    rubric_id = Column(String(64), nullable=True)   # matches writing_rubric item id
    score = Column(Integer, nullable=False)         # e.g. 0/1/2/3
    max_score = Column(Integer, nullable=False, default=3)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class OridBadgeEvent(Base):
    """One row per badge earned per user per session per week. Append-only research log."""

    __tablename__ = "orid_badge_events"
    __table_args__ = (
        UniqueConstraint("user_id", "session_id", "week", "badge_id", name="uq_badge_user_session_week_badge"),
        Index("ix_orid_badge_events_user_week", "user_id", "week"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("orid_sessions.id"), nullable=False)
    reading_id = Column(UUID(as_uuid=True), ForeignKey("readings.id"), nullable=True)
    week = Column(Integer, nullable=False)
    task_type = Column(String(32), nullable=True)    # orid_stage / synthesis
    condition = Column(String(32), nullable=True)    # genai / control
    badge_id = Column(String(32), nullable=False)    # badge_start / badge_30(銅O) / badge_60(銀ORI) / badge_90(金ORID)
    total_score = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    feedback_count = Column(Integer, nullable=True, default=0)
    prompt_view_count = Column(Integer, nullable=True, default=0)
    used_feedback_or_prompt = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
