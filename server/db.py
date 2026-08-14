"""数据库引擎 / 会话 / Base（同步 SQLAlchemy 2.0）。

落库是评测完成后的快速批量写，本地单人场景下同步 session 足够；``MEDEVAL_DATABASE_URL`` 配置化，
未来上服务器多人时切 Postgres 仅改连接串。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, select, text, update
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
        connect_args = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(database_url, future=True, connect_args=connect_args)
    if database_url.startswith("sqlite"):
        # 批量归因会有 3 个并发 Case：WAL 允许读取证据与逐条写回并行，
        # busy_timeout 则让极短的写竞争等待，而不是直接报 database is locked。
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            connection.exec_driver_sql("PRAGMA synchronous=NORMAL")
            connection.exec_driver_sql("PRAGMA busy_timeout=30000")
    return engine


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
    _migrate_benchmark_updated_at(engine)
    _migrate_legacy_open_api_key(engine)
    _migrate_case_list_display_columns(engine)
    _migrate_case_judge_error(engine)
    _migrate_eval_run_trigger_type(engine)
    _migrate_eval_run_scheduled_evaluation_id(engine)
    _migrate_attribution_task_item_analysis(engine)
    _migrate_attribution_task_active_index(engine)


def _migrate_benchmark_updated_at(engine) -> None:
    """为历史 Benchmark 增加更新时间，并以创建时间作为初始值。"""
    inspector = inspect(engine)
    if "benchmark" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("benchmark")}
    if "updated_at" not in columns:
        # SQLite 不允许 ALTER TABLE 时增加 CURRENT_TIMESTAMP 这类非常量默认值，
        # 因此先增加普通列，再统一回填；新库由 ORM 定义直接带默认值。
        with engine.begin() as connection:
            column_type = (
                "TIMESTAMP WITHOUT TIME ZONE"
                if engine.dialect.name == "postgresql"
                else "DATETIME"
            )
            connection.exec_driver_sql(
                f"ALTER TABLE benchmark ADD COLUMN updated_at {column_type}"
            )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE benchmark SET updated_at = created_at "
                "WHERE updated_at IS NULL"
            )
        )


def _migrate_attribution_task_item_analysis(engine) -> None:
    """为已存在的归因任务明细补充独立结果快照列。"""
    inspector = inspect(engine)
    if "attribution_task_item" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("attribution_task_item")}
    if "analysis_json" not in columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE attribution_task_item ADD COLUMN analysis_json JSON"
            )

    # 旧版本只在 CaseResultRow 上保存“最新一次归因”。升级时为历史成功任务补一份
    # 可查看快照；此后新任务会直接保存自己的结果，不再互相覆盖。
    from .models_db import AttributionTask, AttributionTaskItem, CaseResultRow
    from .services.case_attribution import get_stored_attribution

    maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with maker.begin() as session:
        legacy_items = session.execute(
            select(AttributionTaskItem, AttributionTask.run_id)
            .join(AttributionTask, AttributionTask.id == AttributionTaskItem.task_id)
            .where(
                AttributionTaskItem.status == "success",
                AttributionTaskItem.analysis_json.is_(None),
            )
        ).all()
        for item, run_id in legacy_items:
            row = session.scalar(
                select(CaseResultRow).where(
                    CaseResultRow.run_id == run_id,
                    CaseResultRow.sample_id == item.sample_id,
                )
            )
            if row is None:
                continue
            stored = get_stored_attribution(dict(row.detail_json or {}))
            if stored.get("available"):
                item.analysis_json = stored


def _migrate_attribution_task_active_index(engine) -> None:
    """保证同一评测最多只有一个排队中或执行中的归因任务。"""
    inspector = inspect(engine)
    if "attribution_task" not in inspector.get_table_names():
        return

    from datetime import datetime

    from .models_db import AttributionTask, AttributionTaskItem

    maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with maker.begin() as session:
        active = list(session.scalars(
            select(AttributionTask)
            .where(AttributionTask.status.in_(("queued", "running")))
            .order_by(AttributionTask.run_id, AttributionTask.id.desc())
        ))
        retained_runs: set[int] = set()
        for task in active:
            if task.run_id not in retained_runs:
                retained_runs.add(task.run_id)
                continue
            task.status = "failed"
            task.error_msg = "升级时发现同一评测存在重复进行中的归因任务，已自动终止较早任务"
            task.finished_at = datetime.utcnow()
            session.execute(
                update(AttributionTaskItem)
                .where(
                    AttributionTaskItem.task_id == task.id,
                    AttributionTaskItem.status.in_(("pending", "running")),
                )
                .values(
                    status="failed",
                    error_msg="所属重复归因任务已被自动终止",
                    finished_at=datetime.utcnow(),
                )
            )

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_attribution_task_active_run "
            "ON attribution_task (run_id) WHERE status IN ('queued', 'running')"
        )


def _migrate_eval_run_trigger_type(engine) -> None:
    """为历史评测记录补齐来源字段，历史记录统一视作人工发起。"""
    inspector = inspect(engine)
    if "eval_run" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("eval_run")}
    if "trigger_type" in columns:
        return
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE eval_run ADD COLUMN trigger_type VARCHAR(20) DEFAULT 'manual'"
        )
        connection.execute(
            text("UPDATE eval_run SET trigger_type = 'manual' WHERE trigger_type IS NULL")
        )


def _migrate_eval_run_scheduled_evaluation_id(engine) -> None:
    """给定时评测 run 补上来源任务，并按旧任务名称安全回填历史关联。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if not {"eval_run", "scheduled_evaluation"}.issubset(tables):
        return
    columns = {column["name"] for column in inspector.get_columns("eval_run")}
    if "scheduled_evaluation_id" not in columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE eval_run ADD COLUMN scheduled_evaluation_id INTEGER"
            )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_eval_run_scheduled_evaluation_id "
            "ON eval_run (scheduled_evaluation_id)"
        )

    # 早期定时 run 没有外键，但名称固定为“任务名 · [版本] · 定时 时间”。只回填
    # 满足该精确前缀的记录，避免把人工同名评测误归入某个定时任务。
    from .models_db import EvalRun, ScheduledEvaluation

    maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with maker.begin() as session:
        tasks = list(session.scalars(select(ScheduledEvaluation)))
        for task in tasks:
            escaped_name = task.name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            session.execute(
                update(EvalRun)
                .where(
                    EvalRun.trigger_type == "scheduled",
                    EvalRun.scheduled_evaluation_id.is_(None),
                    EvalRun.name.like(f"{escaped_name} · %", escape="\\"),
                )
                .values(scheduled_evaluation_id=task.id)
            )


def _migrate_legacy_open_api_key(engine) -> None:
    """将旧版单一 OpenAPI Key 平滑迁移为一把独立授权的 Key。

    旧表只会保留在已使用过早期页面配置的实例中。迁移按摘要去重，因此应用后续
    重启不会重复创建；保留旧值可避免现有自动化调用因升级而中断。
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if not {"open_api_key_config", "open_api_access_key"}.issubset(tables):
        return
    legacy_columns = {
        column["name"] for column in inspector.get_columns("open_api_key_config")
    }
    if not {"api_key", "updated_by"}.issubset(legacy_columns):
        return

    import hashlib

    with engine.begin() as connection:
        legacy = connection.execute(
            text("SELECT api_key, updated_by FROM open_api_key_config WHERE id = 1")
        ).mappings().first()
        raw_key = str(legacy["api_key"] or "").strip() if legacy else ""
        if not raw_key:
            return
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        exists = connection.execute(
            text("SELECT 1 FROM open_api_access_key WHERE key_hash = :key_hash"),
            {"key_hash": key_hash},
        ).first()
        if exists:
            return

        name = "迁移的历史 Key"
        suffix = 2
        while connection.execute(
            text("SELECT 1 FROM open_api_access_key WHERE name = :name"), {"name": name}
        ).first():
            name = f"迁移的历史 Key {suffix}"
            suffix += 1
        connection.execute(
            text(
                "INSERT INTO open_api_access_key "
                "(name, api_key, key_prefix, key_hash, permissions, created_by) "
                "VALUES (:name, :api_key, :key_prefix, :key_hash, :permissions, :created_by)"
            ),
            {
                "name": name,
                "api_key": raw_key,
                "key_prefix": f"{raw_key[:14]}…",
                "key_hash": key_hash,
                "permissions": '["benchmarks:read", "judge_models:read", '
                '"evaluations:create", "evaluations:read"]',
                "created_by": legacy["updated_by"],
            },
        )


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
        ("case_type", "VARCHAR(200)"),
        ("n_turns", "INTEGER"),
        ("rag_status", "VARCHAR(20)"),
        ("ttft_ms", "FLOAT"),
    ]
    missing = [(name, ddl) for name, ddl in missing if name not in existing]

    # DDL 名称固定在上方，不拼接外部输入；SQLite/PostgreSQL 均支持 ADD COLUMN。
    if missing:
        with engine.begin() as connection:
            for name, ddl in missing:
                connection.exec_driver_sql(f"ALTER TABLE case_result ADD COLUMN {name} {ddl}")

        from .models_db import CaseResultRow
        from .services.case_query import (
            case_n_turns_from_detail,
            case_rag_status_from_detail,
            case_type_from_detail,
            case_ttft_ms_from_detail,
        )

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
                        "case_type": case_type_from_detail(detail),
                        "n_turns": case_n_turns_from_detail(detail),
                        "rag_status": case_rag_status_from_detail(detail),
                        "ttft_ms": case_ttft_ms_from_detail(detail),
                    }
                    for row_id, detail in rows
                ],
            )

    inspector = inspect(engine)
    if "eval_run" not in inspector.get_table_names():
        return
    run_columns = {column["name"] for column in inspector.get_columns("eval_run")}
    if "ttft_summary" not in run_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE eval_run ADD COLUMN ttft_summary JSON")
        from .models_db import EvalRun

        maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
        with maker.begin() as session:
            session.execute(
                update(EvalRun)
                .where(EvalRun.ttft_summary.is_(None))
                .values(ttft_summary={})
            )

    inspector = inspect(engine)
    run_columns = {column["name"] for column in inspector.get_columns("eval_run")}
    if "by_case_type" not in run_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE eval_run ADD COLUMN by_case_type JSON")

        from .models_db import CaseResultRow, EvalRun

        maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
        with maker.begin() as session:
            grouped: dict[int, dict[str, dict[str, int]]] = {}
            rows = session.execute(
                select(
                    CaseResultRow.run_id,
                    CaseResultRow.case_type,
                    CaseResultRow.release_passed,
                )
            ).all()
            for run_id, case_type, release_passed in rows:
                label = str(case_type or "").strip() or "未分类"
                bucket = grouped.setdefault(run_id, {}).setdefault(
                    label, {"total": 0, "passed": 0}
                )
                bucket["total"] += 1
                bucket["passed"] += int(bool(release_passed))
            for run in session.scalars(select(EvalRun)):
                run.by_case_type = grouped.get(run.id, {})


def _migrate_case_judge_error(engine) -> None:
    """为历史八维调用异常补齐可筛选的判分异常标记。"""
    inspector = inspect(engine)
    if "case_result" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("case_result")}
    if "judge_error" not in columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE case_result ADD COLUMN judge_error BOOLEAN DEFAULT FALSE"
            )

    from .models_db import CaseResultRow, EvalRun

    maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with maker.begin() as session:
        rows = session.execute(select(CaseResultRow)).scalars().all()
        touched_run_ids: set[int] = set()
        for row in rows:
            detail = dict(row.detail_json or {})
            verdicts = detail.get("verdicts") or []
            judge_error = any(
                isinstance(verdict, dict)
                and str(verdict.get("name") or "").startswith("dimension.")
                and (
                    bool(
                        (verdict.get("details") or {}).get("judge_error")
                        if isinstance(verdict.get("details"), dict)
                        else False
                    )
                    or "八维判分失败" in str(verdict.get("reason") or "")
                )
                for verdict in verdicts
            )
            row.judge_error = judge_error
            if judge_error:
                # 历史记录曾将上游判分故障按 0 分落库。同步修正明细快照与列表标量，
                # 使列表、详情及导出的判定保持一致，也不能再携带伪造的安全风险标签。
                detail["judge_error"] = True
                detail["grade"] = "判分异常"
                detail["composite_score"] = None
                detail["medical_safety_passed"] = True
                detail["release_passed"] = False
                detail["failure_tags"] = []
                row.detail_json = detail
                row.grade = "判分异常"
                row.composite_score = None
                row.medical_safety_passed = True
                row.release_passed = False
                row.failure_tags = []
                touched_run_ids.add(row.run_id)

        # 任务列表读取的是 EvalRun 的汇总标量；对受影响的历史 run 同步修正安全
        # 失败数等统计，避免明细显示“判分异常”而列表仍把它计作安全失败。
        for run_id in touched_run_ids:
            run = session.get(EvalRun, run_id)
            if run is None:
                continue
            run_rows = [row for row in rows if row.run_id == run_id]
            run.total = len(run_rows)
            run.passed = sum(int(row.release_passed) for row in run_rows)
            run.pass_rate = (run.passed / run.total) if run.total else 0.0
            run.medical_safety_failed = sum(
                int(not row.medical_safety_passed) for row in run_rows
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
