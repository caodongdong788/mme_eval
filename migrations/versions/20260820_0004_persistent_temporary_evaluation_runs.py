"""Persist temporary evaluations and group them into daily Open API runs.

Revision ID: 20260820_0004
Revises: 20260820_0003
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0004"
down_revision = "20260820_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    eval_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("eval_run")
    }
    temporary_columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("temporary_evaluation")
    }

    if "temporary_group_date" not in eval_columns:
        op.add_column(
            "eval_run",
            sa.Column("temporary_group_date", sa.String(length=10), nullable=True),
        )
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("eval_run")}
    if "uq_eval_run_temporary_group_date" not in indexes:
        op.create_index(
            "uq_eval_run_temporary_group_date",
            "eval_run",
            ["temporary_group_date"],
            unique=True,
        )

    if "run_id" not in temporary_columns:
        op.add_column(
            "temporary_evaluation",
            sa.Column("run_id", sa.Integer(), nullable=True),
        )
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_temporary_evaluation_run_id",
                "temporary_evaluation",
                "eval_run",
                ["run_id"],
                ["id"],
                ondelete="SET NULL",
            )
    temporary_indexes = {
        item["name"]
        for item in sa.inspect(bind).get_indexes("temporary_evaluation")
    }
    if "ix_temporary_evaluation_run_id" not in temporary_indexes:
        op.create_index(
            "ix_temporary_evaluation_run_id",
            "temporary_evaluation",
            ["run_id"],
        )

    # 兼容旧字段：保留历史 expires_at 数据，但新逻辑不再据此删除、拒绝查询或领取任务。
    if bind.dialect.name != "sqlite":
        op.alter_column("temporary_evaluation", "expires_at", nullable=True)


def downgrade() -> None:
    # 临时评测已成为审计数据，不在回滚时删除或恢复七天清理语义。
    pass
