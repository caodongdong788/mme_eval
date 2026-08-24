"""freeze run scoring standards and pairwise dimensions

Revision ID: 20260824_0006
Revises: 20260824_0005
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260824_0006"
down_revision = "20260824_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in ("eval_run", "scheduled_evaluation", "pairwise_comparison"):
        inspector = sa.inspect(bind)
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "scoring_standard" not in columns:
            op.add_column(
                table,
                sa.Column(
                    "scoring_standard",
                    sa.String(length=40),
                    nullable=False,
                    server_default="cx_eight_dimension",
                ),
            )
        indexes = {item["name"] for item in sa.inspect(bind).get_indexes(table)}
        index_name = f"ix_{table}_scoring_standard"
        if index_name not in indexes:
            op.create_index(index_name, table, ["scoring_standard"], unique=False)


def downgrade() -> None:
    for table in ("pairwise_comparison", "scheduled_evaluation", "eval_run"):
        op.drop_index(f"ix_{table}_scoring_standard", table_name=table)
        op.drop_column(table, "scoring_standard")
