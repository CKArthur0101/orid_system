"""add orid_post_test_scores table

Revision ID: f1e2d3c4b5a6
Revises: e0f1a2b3c4d5
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "f1e2d3c4b5a6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orid_post_test_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("grader_id", UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("stage", sa.String(4), nullable=False),
        sa.Column("rubric_id", sa.String(64), nullable=True),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("max_score", sa.Integer, nullable=False, server_default="3"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_post_test_student_id", "orid_post_test_scores", ["student_id"])
    op.create_index("ix_post_test_grader_id", "orid_post_test_scores", ["grader_id"])
    op.create_index("ix_post_test_class_id", "orid_post_test_scores", ["class_id"])
    op.create_unique_constraint(
        "uq_post_test_student_week_stage",
        "orid_post_test_scores",
        ["student_id", "week", "stage"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_post_test_student_week_stage", "orid_post_test_scores", type_="unique")
    op.drop_index("ix_post_test_class_id", table_name="orid_post_test_scores")
    op.drop_index("ix_post_test_grader_id", table_name="orid_post_test_scores")
    op.drop_index("ix_post_test_student_id", table_name="orid_post_test_scores")
    op.drop_table("orid_post_test_scores")
