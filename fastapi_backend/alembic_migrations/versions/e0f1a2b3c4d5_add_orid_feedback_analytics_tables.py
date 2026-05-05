"""add orid feedback analytics tables (DB v0)

Revision ID: e0f1a2b3c4d5
Revises: c4b93f2a1d2e
Create Date: 2026-04-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, None] = "c4b93f2a1d2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orid_stage_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stage", sa.String(1), nullable=False),
        sa.Column("draft", sa.String(4), nullable=False),
        sa.Column("student_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("feedback_strength", sa.String(8), nullable=True),
        sa.Column("condition", sa.String(32), nullable=True),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["orid_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orid_stage_attempts_session_id", "orid_stage_attempts", ["session_id"])
    op.create_index("ix_orid_stage_attempts_user_id", "orid_stage_attempts", ["user_id"])

    op.create_table(
        "orid_feedback_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stage", sa.String(1), nullable=False),
        sa.Column("draft", sa.String(4), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("praise", sa.Text(), nullable=True),
        sa.Column("missing_json", sa.Text(), nullable=True),
        sa.Column("suggestions_json", sa.Text(), nullable=True),
        sa.Column("example", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["attempt_id"], ["orid_stage_attempts.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["orid_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orid_feedback_events_attempt_id", "orid_feedback_events", ["attempt_id"])
    op.create_index("ix_orid_feedback_events_session_id", "orid_feedback_events", ["session_id"])
    op.create_index("ix_orid_feedback_events_user_id", "orid_feedback_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_orid_feedback_events_user_id", table_name="orid_feedback_events")
    op.drop_index("ix_orid_feedback_events_session_id", table_name="orid_feedback_events")
    op.drop_index("ix_orid_feedback_events_attempt_id", table_name="orid_feedback_events")
    op.drop_table("orid_feedback_events")

    op.drop_index("ix_orid_stage_attempts_user_id", table_name="orid_stage_attempts")
    op.drop_index("ix_orid_stage_attempts_session_id", table_name="orid_stage_attempts")
    op.drop_table("orid_stage_attempts")
