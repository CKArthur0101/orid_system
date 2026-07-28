"""add orid_weekly_research_summaries table

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-07-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

# revision identifiers, used by Alembic.
revision: str = "l3m4n5o6p7q8"
down_revision: Union[str, None] = "k2l3m4n5o6p7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orid_weekly_research_summaries",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("session_id", PGUUID(as_uuid=True), sa.ForeignKey("orid_sessions.id"), nullable=False),
        sa.Column("class_id", PGUUID(as_uuid=True), sa.ForeignKey("classes.id"), nullable=True),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("task_type", sa.String(32), nullable=True),
        sa.Column("condition", sa.String(16), nullable=False, server_default="experimental"),
        sa.Column("word_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("save_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("revision_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("guide_use_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("badge_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("orid_score", sa.Float, nullable=True),
        sa.Column("sel_score", sa.Float, nullable=True),
        sa.Column("total_score", sa.Integer, nullable=True),
        sa.Column("is_submitted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("content_fingerprint", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "week", "session_id",
            name="uq_orid_weekly_research_user_week_session",
        ),
    )
    op.create_index("ix_orid_weekly_research_summaries_user_id", "orid_weekly_research_summaries", ["user_id"])
    op.create_index(
        "ix_orid_weekly_research_class_week",
        "orid_weekly_research_summaries",
        ["class_id", "week"],
    )
    op.create_index(
        "ix_orid_weekly_research_condition_week",
        "orid_weekly_research_summaries",
        ["condition", "week"],
    )


def downgrade() -> None:
    op.drop_index("ix_orid_weekly_research_condition_week", table_name="orid_weekly_research_summaries")
    op.drop_index("ix_orid_weekly_research_class_week", table_name="orid_weekly_research_summaries")
    op.drop_index("ix_orid_weekly_research_summaries_user_id", table_name="orid_weekly_research_summaries")
    op.drop_table("orid_weekly_research_summaries")
