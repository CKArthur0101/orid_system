"""orid_week_submissions dedupe+unique; orid_messages -> orid_chat_messages

Revision ID: h9c0d1e2f3a4
Revises: g7a8b9c0d1e2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h9c0d1e2f3a4"
down_revision: Union[str, None] = "g7a8b9c0d1e2"
branch_labels: Sequence[str] | None = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1) Writing table: dedupe by (user_id, session_id, week), keep latest created_at ──
    op.execute(
        sa.text(
            """
            WITH ranked AS (
              SELECT id,
                     ROW_NUMBER() OVER (
                       PARTITION BY user_id, session_id, week
                       ORDER BY created_at DESC
                     ) AS rn
              FROM orid_writings
            )
            DELETE FROM orid_writings o
            USING ranked r
            WHERE o.id = r.id AND r.rn > 1;
            """
        )
    )
    op.rename_table("orid_writings", "orid_week_submissions")
    op.add_column(
        "orid_week_submissions",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text("UPDATE orid_week_submissions SET updated_at = created_at"))
    op.alter_column(
        "orid_week_submissions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.create_unique_constraint(
        "uq_orid_week_submissions_user_session_week",
        "orid_week_submissions",
        ["user_id", "session_id", "week"],
    )
    op.execute(
        sa.text(
            "COMMENT ON TABLE orid_week_submissions IS "
            "'Official ORID writing JSON per user/session/week; re-submit overwrites the same row.'"
        )
    )
    op.execute(
        sa.text(
            "COMMENT ON COLUMN orid_week_submissions.created_at IS "
            "'First time this user submitted writing for this session+week.'"
        )
    )
    op.execute(
        sa.text(
            "COMMENT ON COLUMN orid_week_submissions.updated_at IS "
            "'Last overwrite when the student submitted again.'"
        )
    )

    # ── 2) Chat messages rename (one row per message, full conversation order) ──
    op.rename_table("orid_messages", "orid_chat_messages")
    op.execute(
        sa.text(
            "COMMENT ON TABLE orid_chat_messages IS "
            "'ORID + writing-coach chat messages; order by session_id and created_at.'"
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_orid_week_submissions_user_session_week",
        "orid_week_submissions",
        type_="unique",
    )
    op.drop_column("orid_week_submissions", "updated_at")
    op.rename_table("orid_week_submissions", "orid_writings")
    op.rename_table("orid_chat_messages", "orid_messages")
