"""数据库引擎 / 会话 / Base（同步 SQLAlchemy 2.0）。

落库是评测完成后的快速批量写，本地单人场景下同步 session 足够；``MEDEVAL_DATABASE_URL`` 配置化，
未来上服务器多人时切 Postgres 仅改连接串。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, select
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


def init_db(settings: Settings | None = None) -> None:
    """按当前 ORM 从空数据库建表，并补齐轻量列表所需的兼容列。"""
    engine = init_engine(settings)
    from . import models_db  # noqa: F401  触发 ORM 表注册

    Base.metadata.create_all(engine)
    _migrate_case_list_display_columns(engine)


def _migrate_case_list_display_columns(engine) -> None:
    """为既有库补齐 Case 列表标量列，并在首次升级时一次性回填。

    旧版列表每次都从 ``detail_json`` 提取轮数及 RAG 状态；其中包含 Langfuse 原始
    prompt/输出时，95 条用例也会产生数秒延迟。新列只在首次部署时读取一次历史 JSON，
    后续列表查询完全不访问该大字段。
    """
    inspector = inspect(engine)
    if "case_result" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("case_result")}
    missing = [
        ("n_turns", "INTEGER"),
        ("rag_status", "VARCHAR(20)"),
    ]
    missing = [(name, ddl) for name, ddl in missing if name not in existing]
    if not missing:
        return

    # DDL 名称固定在上方，不拼接外部输入；SQLite/PostgreSQL 均支持 ADD COLUMN。
    with engine.begin() as connection:
        for name, ddl in missing:
            connection.exec_driver_sql(f"ALTER TABLE case_result ADD COLUMN {name} {ddl}")

    from .models_db import CaseResultRow
    from .services.case_query import case_n_turns_from_detail, case_rag_status_from_detail

    maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with maker.begin() as session:
        rows = session.execute(
            select(CaseResultRow.id, CaseResultRow.detail_json)
        ).all()
        session.bulk_update_mappings(
            CaseResultRow,
            [
                {
                    "id": row_id,
                    "n_turns": case_n_turns_from_detail(detail),
                    "rag_status": case_rag_status_from_detail(detail),
                }
                for row_id, detail in rows
            ],
        )


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
