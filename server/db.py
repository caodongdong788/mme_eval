"""数据库引擎 / 会话 / Base（同步 SQLAlchemy 2.0）。

落库是评测完成后的快速批量写，本地单人场景下同步 session 足够；``MEDEVAL_DATABASE_URL`` 配置化，
未来上服务器多人时切 Postgres 仅改连接串。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
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
    """按当前 ORM 从空数据库建表；本版本不迁移旧数据库结构。"""
    engine = init_engine(settings)
    from . import models_db  # noqa: F401  触发 ORM 表注册

    Base.metadata.create_all(engine)


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
