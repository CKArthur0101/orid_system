"""add book_unit to orid_sessions for cross-week session reuse

Revision ID: g7a8b9c0d1e2
Revises: f1e2d3c4b5a6
"""
from alembic import op
import sqlalchemy as sa

revision = "g7a8b9c0d1e2"
down_revision = "f1e2d3c4b5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orid_sessions", sa.Column("book_unit", sa.Integer(), nullable=True))
    op.create_index(
        "ix_orid_sessions_user_book_unit",
        "orid_sessions",
        ["user_id", "book_unit"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_orid_sessions_user_book_unit", table_name="orid_sessions")
    op.drop_column("orid_sessions", "book_unit")
