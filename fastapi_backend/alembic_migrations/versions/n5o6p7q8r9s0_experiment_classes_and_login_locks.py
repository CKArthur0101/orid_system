"""experiment class archive, seat numbers, and login locks

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-10-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "n5o6p7q8r9s0"
down_revision: Union[str, None] = "m4n5o6p7q8r9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("classes", sa.Column("study_condition", sa.String(length=16), nullable=True))
    op.add_column("classes", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "uq_classes_year_external_code",
        "classes",
        ["year", "external_code"],
        unique=True,
        postgresql_where=sa.text("external_code IS NOT NULL"),
    )
    op.add_column("student_class_memberships", sa.Column("seat_no", sa.Integer(), nullable=True))
    op.create_index(
        "uq_student_class_memberships_class_seat",
        "student_class_memberships",
        ["class_id", "seat_no"],
        unique=True,
        postgresql_where=sa.text("seat_no IS NOT NULL"),
    )
    op.create_table(
        "login_locks",
        sa.Column("login_id", sa.String(length=128), nullable=False),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("login_id"),
    )
    op.create_table(
        "experiment_import_batches",
        sa.Column("id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("created_by", PGUUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_login_ids", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("experiment_import_batches")
    op.drop_table("login_locks")
    op.drop_index("uq_student_class_memberships_class_seat", table_name="student_class_memberships")
    op.drop_column("student_class_memberships", "seat_no")
    op.drop_index("uq_classes_year_external_code", table_name="classes")
    op.drop_column("classes", "archived_at")
    op.drop_column("classes", "study_condition")
