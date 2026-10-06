"""add privacy-minimized ORID safety event log

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-09-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, None] = "l3m4n5o6p7q8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orid_safety_events",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("session_id", PGUUID(as_uuid=True), sa.ForeignKey("orid_sessions.id"), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(4), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("text_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_orid_safety_events_user_id", "orid_safety_events", ["user_id"])
    op.create_index("ix_orid_safety_events_session_id", "orid_safety_events", ["session_id"])
    op.create_index(
        "ix_orid_safety_events_user_created_at",
        "orid_safety_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_orid_safety_events_session_created_at",
        "orid_safety_events",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_orid_safety_events_level_created_at",
        "orid_safety_events",
        ["level", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_orid_safety_events_level_created_at", table_name="orid_safety_events")
    op.drop_index("ix_orid_safety_events_session_created_at", table_name="orid_safety_events")
    op.drop_index("ix_orid_safety_events_user_created_at", table_name="orid_safety_events")
    op.drop_index("ix_orid_safety_events_session_id", table_name="orid_safety_events")
    op.drop_index("ix_orid_safety_events_user_id", table_name="orid_safety_events")
    op.drop_table("orid_safety_events")
