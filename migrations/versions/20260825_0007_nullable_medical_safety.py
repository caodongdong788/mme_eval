"""allow scoring standards without a medical safety gate

Revision ID: 20260825_0007
Revises: 20260824_0006
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260825_0007"
down_revision = "20260824_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("case_result") as batch_op:
        batch_op.alter_column(
            "medical_safety_passed",
            existing_type=sa.Boolean(),
            nullable=True,
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE case_result SET medical_safety_passed = 1 "
            "WHERE medical_safety_passed IS NULL"
        )
    )
    with op.batch_alter_table("case_result") as batch_op:
        batch_op.alter_column(
            "medical_safety_passed",
            existing_type=sa.Boolean(),
            nullable=False,
        )
