"""数据库引擎 / 会话 / Base（同步 SQLAlchemy 2.0）。

落库是评测完成后的快速批量写，本地单人场景下同步 session 足够；``MEDEVAL_DATABASE_URL`` 配置化，
未来上服务器多人时切 Postgres 仅改连接串。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import json

from sqlalchemy import create_engine, inspect, select, text, update
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import PROJECT_ROOT, Settings, get_settings


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
    """通过 Alembic 升级数据库；旧库只在首次接管时执行一次兼容迁移。"""
    engine = init_engine(settings)
    from . import models_db  # noqa: F401  触发 ORM 表注册

    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables and tables:
        # 2026-08-20 之前的安装没有版本表。先按旧逻辑补齐到 baseline，之后所有
        # 发布只执行 Alembic revision，不再每次启动扫描/ALTER 历史表。
        Base.metadata.create_all(engine)
        _run_legacy_schema_adoption(engine)
        _run_alembic(engine, stamp_only=True)
        return
    _run_alembic(engine, stamp_only=False)


def _run_alembic(engine, *, stamp_only: bool) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        if stamp_only:
            command.stamp(config, "head")
        else:
            command.upgrade(config, "head")


def _run_legacy_schema_adoption(engine) -> None:
    """仅用于无 alembic_version 的历史安装，完成后立即 stamp baseline。"""
    Base.metadata.create_all(engine)
    _migrate_benchmark_updated_at(engine)
    _migrate_legacy_open_api_key(engine)
    _migrate_case_list_display_columns(engine)
    # RAG 历史回填是维护动作，不再放到每次进程启动路径。新增记录会在写入时
    # 直接保存 rag_status；旧库首次增加列表标量列时也已完成一次回填。
    _migrate_case_judge_error(engine, backfill_existing=False)
    _migrate_eval_run_trigger_type(engine)
    _migrate_scheduled_evaluation_auto_attribution(engine)
    _migrate_eval_run_scheduled_evaluation_id(engine)
    _migrate_attribution_task_item_attempt_count(engine)
    _migrate_attribution_task_item_analysis(engine)
    _migrate_attribution_task_streaming(engine)
    _migrate_attribution_task_active_index(engine)
    _migrate_run_submission_integrity(engine)


def _migrate_run_submission_integrity(engine) -> None:
    """补齐 Run 所有权、定时 occurrence 与队列幂等字段及约束。

    历史版本可能已经留下同一 Run 的多个活跃任务。迁移时保留一个 running
    优先、ID 最小的任务，并把其余任务收敛为 cancelled，再建立唯一索引。
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "eval_run" in tables:
        columns = {column["name"] for column in inspector.get_columns("eval_run")}
        with engine.begin() as connection:
            if "scheduled_occurrence_key" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE eval_run ADD COLUMN scheduled_occurrence_key VARCHAR(80)"
                )
            if "open_api_key_id" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE eval_run ADD COLUMN open_api_key_id INTEGER"
                )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_eval_run_open_api_key_id "
                "ON eval_run (open_api_key_id)"
            )
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_eval_run_scheduled_occurrence "
                "ON eval_run (scheduled_evaluation_id, scheduled_occurrence_key)"
            )

    if "evaluation_job" in tables:
        columns = {column["name"] for column in inspector.get_columns("evaluation_job")}
        with engine.begin() as connection:
            if "active_key" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE evaluation_job ADD COLUMN active_key VARCHAR(240)"
                )
            rows = connection.execute(
                text(
                    "SELECT id, run_id, kind, payload, status FROM evaluation_job "
                    "WHERE status IN ('queued', 'running') ORDER BY id"
                )
            ).mappings().all()
            grouped: dict[str, list[dict]] = {}
            for row in rows:
                kind = str(row["kind"] or "")
                if kind in {"evaluation", "resume", "rejudge", "cases_retry"}:
                    key = f"run:{int(row['run_id'])}:execution"
                elif kind == "attribution":
                    payload = row["payload"] or {}
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except ValueError:
                            payload = {}
                    task_id = int((payload or {}).get("attribution_task_id") or 0)
                    if not task_id:
                        continue
                    key = f"attribution:{task_id}"
                else:
                    continue
                grouped.setdefault(key, []).append(dict(row))

            for key, candidates in grouped.items():
                candidates.sort(
                    key=lambda item: (0 if item["status"] == "running" else 1, item["id"])
                )
                keep = candidates[0]
                connection.execute(
                    text("UPDATE evaluation_job SET active_key=:key WHERE id=:id"),
                    {"key": key, "id": keep["id"]},
                )
                duplicate_ids = [item["id"] for item in candidates[1:]]
                for duplicate_id in duplicate_ids:
                    connection.execute(
                        text(
                            "UPDATE evaluation_job SET status='cancelled', active_key=NULL, "
                            "lease_owner=NULL, lease_expires_at=NULL, finished_at=CURRENT_TIMESTAMP, "
                            "error_msg='重复活跃任务已由幂等迁移取消' WHERE id=:id"
                        ),
                        {"id": duplicate_id},
                    )
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_evaluation_job_active_key "
                "ON evaluation_job (active_key)"
            )

    if "open_api_access_key" in tables:
        # 管理端要求后续随时查看完整 Key。只对升级前遗留的明文做一次原位加密；
        # 已是版本化密文或旧版本已经清空的记录不反复写表。
        from .secret_codec import encrypt_recoverable_secret, is_encrypted_recoverable_secret

        with engine.begin() as connection:
            rows = connection.execute(
                text(
                    "SELECT id, api_key FROM open_api_access_key "
                    "WHERE api_key IS NOT NULL AND api_key<>''"
                )
            ).mappings().all()
            for row in rows:
                raw_value = str(row["api_key"] or "")
                if is_encrypted_recoverable_secret(raw_value):
                    continue
                connection.execute(
                    text("UPDATE open_api_access_key SET api_key=:value WHERE id=:id"),
                    {
                        "id": row["id"],
                        "value": encrypt_recoverable_secret(raw_value),
                    },
                )


def _migrate_benchmark_updated_at(engine) -> None:
    """为历史 Benchmark 增加更新时间，并以创建时间作为初始值。"""
    inspector = inspect(engine)
    if "benchmark" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("benchmark")}
    column_added = "updated_at" not in columns
    if column_added:
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
    # 只在真正增加列时回填。正常重启不能反复触发全表 UPDATE 扫描。
    if column_added:
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
    column_added = "analysis_json" not in columns
    if column_added:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE attribution_task_item ADD COLUMN analysis_json JSON"
            )
    else:
        # 旧快照回填仅属于加列迁移；重复执行会在每次启动时联表读取大 JSON。
        return

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


def _migrate_attribution_task_item_attempt_count(engine) -> None:
    """为历史归因明细补充重试计数与运行期状态列，且早于 ORM 查询。"""
    inspector = inspect(engine)
    if "attribution_task_item" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("attribution_task_item")}
    with engine.begin() as connection:
        if "attempt_count" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE attribution_task_item "
                "ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"
            )
        if "runtime_status" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE attribution_task_item "
                "ADD COLUMN runtime_status VARCHAR(40) NOT NULL DEFAULT 'pending'"
            )
        if "runtime_message" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE attribution_task_item "
                "ADD COLUMN runtime_message TEXT NOT NULL DEFAULT ''"
            )
        if "model_attempt" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE attribution_task_item "
                "ADD COLUMN model_attempt INTEGER NOT NULL DEFAULT 0"
            )
        if "retry_count" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE attribution_task_item "
                "ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"
            )
        if "runtime_updated_at" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE attribution_task_item "
                "ADD COLUMN runtime_updated_at DATETIME"
            )


def _migrate_attribution_task_streaming(engine) -> None:
    """为定时评测的逐 Case 流水线归因补充接收状态。"""
    inspector = inspect(engine)
    if "attribution_task" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("attribution_task")}
    with engine.begin() as connection:
        if "is_streaming" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE attribution_task "
                "ADD COLUMN is_streaming BOOLEAN NOT NULL DEFAULT FALSE"
            )
        if "intake_open" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE attribution_task "
                "ADD COLUMN intake_open BOOLEAN NOT NULL DEFAULT FALSE"
            )


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
    column_added = "scheduled_evaluation_id" not in columns
    if column_added:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE eval_run ADD COLUMN scheduled_evaluation_id INTEGER"
            )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_eval_run_scheduled_evaluation_id "
            "ON eval_run (scheduled_evaluation_id)"
        )
    if not column_added:
        return

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


def _migrate_scheduled_evaluation_auto_attribution(engine) -> None:
    """为已有定时任务补齐自动归因配置，默认维持关闭。"""
    inspector = inspect(engine)
    if "scheduled_evaluation" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("scheduled_evaluation")}
    grades_added = "auto_attribution_grades" not in columns
    with engine.begin() as connection:
        if "auto_attribution_enabled" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE scheduled_evaluation "
                "ADD COLUMN auto_attribution_enabled BOOLEAN DEFAULT FALSE"
            )
        if "auto_attribution_grades" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE scheduled_evaluation ADD COLUMN auto_attribution_grades JSON"
            )
        if "auto_attribution_model_id" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE scheduled_evaluation ADD COLUMN auto_attribution_model_id INTEGER"
            )
        if grades_added:
            connection.execute(
                text(
                    "UPDATE scheduled_evaluation "
                    "SET auto_attribution_grades = :grades "
                    "WHERE auto_attribution_grades IS NULL"
                ),
                {"grades": '["不合格"]'},
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

    from .secret_codec import encrypt_recoverable_secret

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
                "api_key": encrypt_recoverable_secret(raw_key),
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


def _backfill_case_rag_status_from_audits(engine) -> None:
    """修复历史上因 Langfuse 尚未同步而保存为 unknown 的 RAG 状态。

    仅检查 unknown 行，避免恢复旧版列表逐条读取大 JSON 的性能问题。审计快照
    由 cx-agent 直接保存，能够在 Langfuse 延迟或截断时给出可靠的命中结论。
    """
    inspector = inspect(engine)
    if "case_result" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("case_result")}
    if "rag_status" not in columns:
        return

    from .models_db import CaseResultRow
    from .services.case_query import case_rag_status_from_detail

    maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with maker.begin() as session:
        rows = session.execute(
            select(CaseResultRow.id, CaseResultRow.detail_json).where(
                CaseResultRow.rag_status == "unknown"
            )
        ).all()
        updates = [
            {"id": row_id, "rag_status": status}
            for row_id, detail in rows
            if (status := case_rag_status_from_detail(detail)) != "unknown"
        ]
        if updates:
            session.bulk_update_mappings(CaseResultRow, updates)


def _migrate_case_judge_error(engine, *, backfill_existing: bool = True) -> None:
    """为历史八维/指南调用异常补齐可筛选的判分异常标记。

    ``init_db`` 使用 ``backfill_existing=False``：若列已经存在，说明历史版本已
    完成过回填，正常启动必须立即返回。显式维护脚本和单元测试仍可使用默认值
    重新校准历史数据。
    """
    inspector = inspect(engine)
    if "case_result" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("case_result")}
    column_added = "judge_error" not in columns
    if column_added:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE case_result ADD COLUMN judge_error BOOLEAN DEFAULT FALSE"
            )
    elif not backfill_existing:
        return

    from .models_db import CaseResultRow, EvalRun

    maker = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with maker.begin() as session:
        rows = session.execute(select(CaseResultRow)).scalars().all()
        touched_run_ids: set[int] = set()
        for row in rows:
            detail = dict(row.detail_json or {})
            verdicts = detail.get("verdicts") or []
            def is_judge_error(verdict: object) -> bool:
                if not isinstance(verdict, dict):
                    return False
                details = verdict.get("details")
                return (
                    bool(details.get("judge_error")) if isinstance(details, dict) else False
                ) or (
                    "八维判分失败" in str(verdict.get("reason") or "")
                    or "指南判分失败" in str(verdict.get("reason") or "")
                    # 历史版本把模型返回 None/浮点/越界扣分保守折算为满额扣分。
                    # 这不是业务扣分，升级时需一并回填为可重试的判分异常。
                    or "模型返回非法扣分" in str(verdict.get("reason") or "")
                )

            judge_error = any(
                str(verdict.get("name") or "").startswith(("dimension.", "guideline."))
                and is_judge_error(verdict)
                for verdict in verdicts
                if isinstance(verdict, dict)
            )
            guideline_errors = {
                str(verdict.get("name") or "").removeprefix("guideline."): str(verdict.get("reason") or "")
                for verdict in verdicts
                if isinstance(verdict, dict)
                and str(verdict.get("name") or "").startswith("guideline.")
                and is_judge_error(verdict)
            }
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
                for score in detail.get("guideline_scores") or []:
                    if not isinstance(score, dict):
                        continue
                    error_reason = guideline_errors.get(str(score.get("id") or ""))
                    if error_reason:
                        score["judge_error"] = True
                        score["judge_error_message"] = error_reason
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
