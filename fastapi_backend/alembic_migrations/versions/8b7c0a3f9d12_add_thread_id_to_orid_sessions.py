"""add thread_id to orid_sessions

Revision ID: 8b7c0a3f9d12
Revises: 9981ddd087c1
Create Date: 2026-02-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8b7c0a3f9d12"
down_revision: Union[str, None] = "9981ddd087c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orid_sessions", sa.Column("thread_id", sa.String(), nullable=True))
    op.create_index("ix_orid_sessions_thread_id", "orid_sessions", ["thread_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orid_sessions_thread_id", table_name="orid_sessions")
    op.drop_column("orid_sessions", "thread_id")
