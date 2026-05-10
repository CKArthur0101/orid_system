"""add user.display_name for student-facing name

Revision ID: i0a1b2c3d4e5
Revises: h9c0d1e2f3a4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "i0a1b2c3d4e5"
down_revision: Union[str, None] = "h9c0d1e2f3a4"
branch_labels: Sequence[str] | None = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("display_name", sa.String(length=128), nullable=True),
    )
    op.execute(
        sa.text(
            'COMMENT ON COLUMN "user".display_name IS '
            "'Shown in UI; student header uses display name + 同學 suffix (fallback to login id).'"
        )
    )
    # Best-effort: demo account renames (idempotent if no match)
    op.execute(
        sa.text(
            """
            UPDATE "user" SET email = '114524020', display_name = '邱振凱'
            WHERE lower(email) = 'arthur.chiu0101@gmail.com'
               OR lower(email) LIKE 'arthur.chiu0101@%'
               OR email = 'arthur.chiu0101@gmail.com';
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE "user" SET email = '114524021', display_name = '林宜萱'
            WHERE lower(email) = 'orid.student@example.com';
            """
        )
    )


def downgrade() -> None:
    op.drop_column("user", "display_name")
