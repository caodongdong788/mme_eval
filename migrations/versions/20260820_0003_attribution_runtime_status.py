"""Persist detailed runtime status for attribution task items.

Revision ID: 20260820_0003
Revises: 20260820_0002
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0003"
down_revision = "20260820_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("attribution_task_item")
    }
    additions = [
        ("runtime_status", sa.Column("runtime_status", sa.String(length=40), nullable=True)),
        ("runtime_message", sa.Column("runtime_message", sa.Text(), nullable=True)),
        ("model_attempt", sa.Column("model_attempt", sa.Integer(), nullable=True)),
        ("retry_count", sa.Column("retry_count", sa.Integer(), nullable=True)),
        ("runtime_updated_at", sa.Column("runtime_updated_at", sa.DateTime(), nullable=True)),
    ]
    for name, column in additions:
        if name not in columns:
            op.add_column("attribution_task_item", column)
    bind.execute(sa.text(
        "UPDATE attribution_task_item SET runtime_status=COALESCE(runtime_status, status), "
        "runtime_message=COALESCE(runtime_message, ''), "
        "model_attempt=COALESCE(model_attempt, 0), retry_count=COALESCE(retry_count, 0)"
    ))


def downgrade() -> None:
    # 保留运行期诊断记录，避免回滚时丢失历史任务信息。
    pass
