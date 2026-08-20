"""旧版单 Key 配置升级到多 Key 的兼容迁移。"""

from __future__ import annotations

from sqlalchemy import text

from server import db as db_mod
from server.secret_codec import decrypt_recoverable_secret


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
                "SELECT name, api_key, key_hash, permissions, created_by "
                "FROM open_api_access_key"
            )
        ).mappings().one()

    assert migrated["name"] == "迁移的历史 Key"
    assert migrated["api_key"].startswith("fernet:v1:")
    assert migrated["api_key"] != "legacy-open-key"
    assert migrated["key_hash"]
    assert migrated["created_by"] == "旧管理员"
    assert "evaluations:create" in migrated["permissions"]

    # 再次初始化不能重复创建。
    db_mod.init_db(settings)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM open_api_access_key")).scalar() == 1


def test_alembic_upgrade_encrypts_existing_recoverable_key(settings):
    """已经接入 baseline 的部署也会通过 0002 数据迁移加密历史明文。"""
    db_mod.init_db(settings)
    engine = db_mod.init_engine(settings)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO open_api_access_key "
                "(name, api_key, key_prefix, key_hash, permissions) "
                "VALUES ('历史可查看 Key', 'plain-before-upgrade', 'plain-before…', "
                "'hash-before-upgrade', :permissions)"
            ),
            {"permissions": '["benchmarks:read"]'},
        )
        connection.execute(
            text(
                "UPDATE alembic_version SET version_num='20260820_0001'"
            )
        )

    db_mod.init_db(settings)

    with engine.connect() as connection:
        stored = connection.execute(
            text(
                "SELECT api_key FROM open_api_access_key "
                "WHERE name='历史可查看 Key'"
            )
        ).scalar_one()
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert stored.startswith("fernet:v1:")
    assert decrypt_recoverable_secret(stored) == "plain-before-upgrade"
    assert revision == "20260820_0003"
