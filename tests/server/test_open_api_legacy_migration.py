"""旧版单 Key 配置升级到多 Key 的兼容迁移。"""

from __future__ import annotations

from sqlalchemy import text

from server import db as db_mod


def test_legacy_open_api_key_becomes_access_key(settings):
    engine = db_mod.init_engine(settings)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE open_api_key_config "
                "(id INTEGER PRIMARY KEY, api_key TEXT, updated_by VARCHAR(100))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO open_api_key_config (id, api_key, updated_by) "
                "VALUES (1, 'legacy-open-key', '旧管理员')"
            )
        )

    db_mod.init_db(settings)
    with engine.connect() as connection:
        migrated = connection.execute(
            text(
                "SELECT name, api_key, permissions, created_by "
                "FROM open_api_access_key"
            )
        ).mappings().one()

    assert migrated["name"] == "迁移的历史 Key"
    assert migrated["api_key"] == "legacy-open-key"
    assert migrated["created_by"] == "旧管理员"
    assert "evaluations:create" in migrated["permissions"]

    # 再次初始化不能重复创建。
    db_mod.init_db(settings)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM open_api_access_key")).scalar() == 1
