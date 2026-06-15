"""数据库引擎 / 会话 / Base（同步 SQLAlchemy 2.0）。

落库是评测完成后的快速批量写，本地单人场景下同步 session 足够；``MEDEVAL_DATABASE_URL`` 配置化，
未来上服务器多人时切 Postgres 仅改连接串。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import JSON, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import Settings, get_settings


class Base(DeclarativeBase):
    """所有 ORM 表的声明基类。"""


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def _make_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        # FastAPI 多线程（threadpool 跑同步路由）下需要关闭 sqlite 的同线程校验。
        connect_args = {"check_same_thread": False}
    return create_engine(database_url, future=True, connect_args=connect_args)


def init_engine(settings: Settings | None = None):
    """初始化全局 engine 与 sessionmaker（幂等）。返回 engine。"""
    global _engine, _SessionLocal
    settings = settings or get_settings()
    if _engine is None:
        _engine = _make_engine(settings.database_url)
        _SessionLocal = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)
    return _engine


def _json_empty_literal(col) -> str:
    """JSON 列的空初值：默认 list 的列用 '[]'，否则 '{}'（保证旧行是合法 JSON 而非 NULL）。"""
    default = col.default
    if default is not None and getattr(default, "arg", None) is list:
        return "[]"
    return "{}"


def _column_add_ddl(col, dialect) -> str | None:
    """为「安全可追加」的列生成 `ALTER TABLE ADD COLUMN` 片段，否则返回 None。

    安全 = 可空 或 带默认值（标量/JSON 默认会落 DEFAULT 子句，让旧行有合理初值）；
    NOT NULL 且无默认的列无法在已有数据上追加，留给完整迁移处理。
    始终以可空形式追加（不写 NOT NULL），避免对存量行报错。
    """
    has_default = col.default is not None or col.server_default is not None
    if not col.nullable and not has_default:
        return None
    try:
        coltype = col.type.compile(dialect=dialect)
    except Exception:
        return None
    ddl = f"{col.name} {coltype}"
    if isinstance(col.type, JSON):
        # JSON 列若留 NULL，响应模型（dict/list）校验会 500；给空 JSON 初值。
        return f"{ddl} DEFAULT '{_json_empty_literal(col)}'"
    default = col.default
    if default is not None and not getattr(default, "is_callable", False):
        arg = getattr(default, "arg", None)
        if isinstance(arg, bool):
            ddl += f" DEFAULT {1 if arg else 0}"
        elif isinstance(arg, (int, float)):
            ddl += f" DEFAULT {arg}"
        elif isinstance(arg, str):
            ddl += f" DEFAULT '{arg}'"
    return ddl


def _ensure_additive_columns(engine) -> None:
    """由 ORM 元数据驱动，对已存在的表幂等补齐缺失的可空/带默认列。

    create_all 只建新表、不给旧表加列；这里 diff ORM 列与库列，把「安全可追加」的列
    `ALTER TABLE ADD COLUMN`。如此新增 ORM 列无需再手工登记迁移表，杜绝列漂移导致的查询 500。
    并对非空 JSON 列回填 NULL→空 JSON，自愈历史上以 NULL 形式补过的列。
    """
    from . import models_db  # noqa: F401  确保 ORM 表已注册到 Base.metadata

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table_name)}
            for col in table.columns:
                if col.name not in present:
                    ddl = _column_add_ddl(col, engine.dialect)
                    if ddl is not None:
                        conn.execute(
                            text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")
                        )
                # 自愈：非空 JSON 列的存量 NULL 回填为合法空 JSON。
                if isinstance(col.type, JSON) and not col.nullable:
                    conn.execute(text(
                        f"UPDATE {table_name} SET {col.name} = '{_json_empty_literal(col)}' "
                        f"WHERE {col.name} IS NULL"
                    ))


def _drop_obsolete_columns(engine) -> None:
    """对已存在表幂等 DROP 已从 ORM 移除的列（SQLite 3.35+）。

    SQLite 无法 DROP 一个仍被索引引用的列（会报 `error in index ... after drop column`），
    故先把引用该列的索引删掉，再 `ALTER TABLE ... DROP COLUMN`。
    """
    obsolete: dict[str, list[str]] = {
        "eval_run": ["by_population", "by_difficulty"],
        "case_result": ["population", "difficulty"],
    }
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, cols in obsolete.items():
            if table_name not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table_name)}
            indexes = inspector.get_indexes(table_name)
            for col in cols:
                if col not in present:
                    continue
                for idx in indexes:
                    if col in (idx.get("column_names") or []) and idx.get("name"):
                        conn.execute(text(f"DROP INDEX IF EXISTS {idx['name']}"))
                conn.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {col}"))


def _ensure_indexes(engine) -> None:
    """对已存在表幂等创建 ORM 中新增的索引（含复合索引）。

    ``create_all`` 只为新建表创建索引，已存在的表不会补建后加的索引；这里按 ORM 元数据
    对每个索引 ``create(checkfirst=True)``，使复合索引在存量 SQLite 库上也能补齐。
    """
    from . import models_db  # noqa: F401  确保 ORM 表已注册到 Base.metadata

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            for index in table.indexes:
                index.create(bind=conn, checkfirst=True)


def init_db(settings: Settings | None = None) -> None:
    """建表（首次启动调用）。导入 models_db 触发表注册后 create_all + 幂等补列/补索引。"""
    engine = init_engine(settings)
    from . import models_db  # noqa: F401  触发 ORM 表注册

    Base.metadata.create_all(engine)
    _drop_obsolete_columns(engine)
    _ensure_additive_columns(engine)
    _ensure_indexes(engine)


def get_sessionmaker() -> sessionmaker[Session]:
    if _SessionLocal is None:
        init_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """事务性会话上下文：正常提交、异常回滚、最终关闭。"""
    maker = get_sessionmaker()
    session = maker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI 依赖：每请求一个会话（提交/回滚/关闭由本函数兜底）。"""
    with session_scope() as session:
        yield session


def reset_engine_for_tests() -> None:
    """测试辅助：丢弃全局 engine/sessionmaker，下次按新 settings 重建。"""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
