"""历史归因明细表升级到可原任务重试结构。"""

from __future__ import annotations

from sqlalchemy import inspect, text

from server import db as db_mod


def test_legacy_attribution_items_add_retry_column_before_orm_queries(settings):
    engine = db_mod.init_engine(settings)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE attribution_task_item ("
                "id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, "
                "sample_id VARCHAR(200), status VARCHAR(20), error_msg TEXT, "
                "started_at DATETIME, finished_at DATETIME)"
            )
        )

    # 回归生产升级路径：create_all 不会为历史表补列，必须由轻量迁移完成，
    # 且 attempt_count 必须早于任何 AttributionTaskItem ORM 查询创建。
    db_mod.init_db(settings)

    columns = {
        column["name"]
        for column in inspect(engine).get_columns("attribution_task_item")
    }
    assert "attempt_count" in columns
    assert "analysis_json" in columns

