"""Add the cx-agent system prompt switch to scheduled evaluations.

Revision ID: 20260824_0005
Revises: 20260820_0004
"""

from alembic import op
import sqlalchemy as sa


revision = "20260824_0005"
down_revision = "20260820_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("scheduled_evaluation")
    }
    if "enable_system_prompt" not in columns:
        op.add_column(
            "scheduled_evaluation",
            sa.Column(
                "enable_system_prompt",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade() -> None:
    # 保留任务运行语义，避免回滚时静默丢失开关配置。
    pass
