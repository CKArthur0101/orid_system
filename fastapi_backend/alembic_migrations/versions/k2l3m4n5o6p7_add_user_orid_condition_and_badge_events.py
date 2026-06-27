"""add user orid_condition and orid_badge_events table

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-06-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "k2l3m4n5o6p7"
down_revision: Union[str, None] = "j1k2l3m4n5o6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add orid_condition and orid_condition_updated_at to user table
    op.add_column(
        "user",
        sa.Column(
            "orid_condition",
            sa.String(16),
            nullable=False,
            server_default="experimental",
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "orid_condition_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Create orid_badge_events table
    from sqlalchemy.dialects.postgresql import UUID as PGUUID
    op.create_table(
        "orid_badge_events",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("session_id", PGUUID(as_uuid=True), sa.ForeignKey("orid_sessions.id"), nullable=False),
        sa.Column("reading_id", PGUUID(as_uuid=True), sa.ForeignKey("readings.id"), nullable=True),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("task_type", sa.String(32), nullable=True),
        sa.Column("condition", sa.String(32), nullable=True),
        sa.Column("badge_id", sa.String(32), nullable=False),
        sa.Column("total_score", sa.Integer, nullable=True),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("feedback_count", sa.Integer, nullable=True, server_default="0"),
        sa.Column("prompt_view_count", sa.Integer, nullable=True, server_default="0"),
        sa.Column("used_feedback_or_prompt", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "user_id", "session_id", "week", "badge_id",
            name="uq_badge_user_session_week_badge",
        ),
    )
    op.create_index("ix_orid_badge_events_user_week", "orid_badge_events", ["user_id", "week"])
    op.create_index("ix_orid_badge_events_user_id", "orid_badge_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_orid_badge_events_user_id", table_name="orid_badge_events")
    op.drop_index("ix_orid_badge_events_user_week", table_name="orid_badge_events")
    op.drop_table("orid_badge_events")
    op.drop_column("user", "orid_condition_updated_at")
    op.drop_column("user", "orid_condition")
