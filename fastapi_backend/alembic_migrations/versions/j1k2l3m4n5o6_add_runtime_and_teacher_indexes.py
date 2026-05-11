"""add runtime and teacher analytics indexes

Revision ID: j1k2l3m4n5o6
Revises: i0a1b2c3d4e5
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "j1k2l3m4n5o6"
down_revision: Union[str, None] = "i0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_orid_sessions_user_book_unit_created_at",
        "orid_sessions",
        ["user_id", "book_unit", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_orid_chat_messages_session_created_at",
        "orid_chat_messages",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_orid_week_submissions_user_week_session",
        "orid_week_submissions",
        ["user_id", "week", "session_id"],
        unique=False,
    )
    op.create_index(
        "ix_student_class_memberships_class_student",
        "student_class_memberships",
        ["class_id", "student_id"],
        unique=False,
    )
    op.create_index(
        "ix_orid_feedback_events_session_stage_created_at",
        "orid_feedback_events",
        ["session_id", "stage", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_orid_feedback_events_session_stage_created_at", table_name="orid_feedback_events")
    op.drop_index("ix_student_class_memberships_class_student", table_name="student_class_memberships")
    op.drop_index("ix_orid_week_submissions_user_week_session", table_name="orid_week_submissions")
    op.drop_index("ix_orid_chat_messages_session_created_at", table_name="orid_chat_messages")
    op.drop_index("ix_orid_sessions_user_book_unit_created_at", table_name="orid_sessions")
