import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func, String, UniqueConstraint
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    reading_id = Column(UUID(as_uuid=True), ForeignKey("readings.id"), nullable=False)

    # ✅ OpenAI Assistants thread id（每個 session 綁一個 thread）
    thread_id = Column(String, nullable=True, index=True)

    condition = Column(String, nullable=True)  # A/B 或 experimental/control
    current_stage = Column(String, default="O", nullable=False)  # O/R/I/D
    stage_turn = Column(Integer, default=0, nullable=False)      # 用來控制幾輪後進下一階段

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
    reading = relationship("Reading")
    messages = relationship("OridMessage", back_populates="session", cascade="all, delete-orphan")


class OridMessage(Base):
    __tablename__ = "orid_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("orid_sessions.id"), nullable=False)

    stage = Column(String, nullable=False)    # O/R/I/D
    sender = Column(String, nullable=False)   # "student" / "ai"
    text = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("OridSession", back_populates="messages")


class OridWriting(Base):
    __tablename__ = "orid_writings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    reading_id = Column(UUID(as_uuid=True), ForeignKey("readings.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("orid_sessions.id"), nullable=False)

    week = Column(Integer, nullable=False)          # 第幾週(1~6)
    content = Column(Text, nullable=False)          # 寫作內容
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClassRoom(Base):
    __tablename__ = "classes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    year = Column(Integer, nullable=False, default=datetime.utcnow().year)
    external_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StudentClassMembership(Base):
    __tablename__ = "student_class_memberships"
    __table_args__ = (UniqueConstraint("student_id", "class_id", name="uq_student_class_membership"),)

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
