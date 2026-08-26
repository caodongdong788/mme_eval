"""cache lightweight attribution summaries on evaluation runs

Revision ID: 20260826_0008
Revises: 20260825_0007
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


revision = "20260826_0008"
down_revision = "20260825_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    existing_columns = {
        column["name"] for column in sa.inspect(connection).get_columns("eval_run")
    }
    # 本项目的测试基线会按当前 ORM 元数据创建表；生产库则由历史迁移创建。
    # 因此只给尚未存在的列补迁移，兼容两种建库方式。
    with op.batch_alter_table("eval_run") as batch_op:
        if "attribution_summary" not in existing_columns:
            batch_op.add_column(sa.Column("attribution_summary", sa.JSON(), nullable=True))
        if "attribution_summary_updated_at" not in existing_columns:
            batch_op.add_column(sa.Column("attribution_summary_updated_at", sa.DateTime(), nullable=True))

    # 一次性回填历史数据。完整归因证据只在迁移时扫描一次；上线后的列表页
    # 只读取 eval_run 上的轻量摘要，不会随着历史任务增加而变慢。
    from server.models_db import EvalRun
    from server.services.attribution_tasks import refresh_run_attribution_summary

    # Alembic owns the outer transaction，因此这里只 flush，不在迁移内部提交。
    session = Session(bind=connection)
    try:
        run_ids = list(session.scalars(sa.select(EvalRun.id)))
        for run_id in run_ids:
            refresh_run_attribution_summary(session, run_id)
        session.flush()
    finally:
        session.close()


def downgrade() -> None:
    connection = op.get_bind()
    existing_columns = {
        column["name"] for column in sa.inspect(connection).get_columns("eval_run")
    }
    with op.batch_alter_table("eval_run") as batch_op:
        if "attribution_summary_updated_at" in existing_columns:
            batch_op.drop_column("attribution_summary_updated_at")
        if "attribution_summary" in existing_columns:
            batch_op.drop_column("attribution_summary")
