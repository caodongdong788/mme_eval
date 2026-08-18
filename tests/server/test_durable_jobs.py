"""数据库评测队列：持久化、租约恢复、取消和 Worker 状态机。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from server.db import session_scope
from server.durable_queue import (
    cancel_job,
    cancel_attribution_job,
    claim_job,
    enqueue_job,
    enqueue_attribution_job,
    finish_job,
    heartbeat_job,
    queue_snapshot,
    reconcile_succeeded_run_statuses,
    reconcile_unqueued_runs,
    requeue_job,
)
from server.durable_jobs import build_job_from_payload
from server.job_specs import attach_job_spec, get_job_spec
from server.jobs import DatabaseJobRunner
from server.models_db import AttributionTask, EvalRun, EvaluationJob
from server.progress import InMemoryProgress
from server.worker import _restore_progress_floor


def _new_run() -> int:
    with session_scope() as session:
        row = EvalRun(run_slug="(pending)", name="durable", status="pending")
        session.add(row)
        session.flush()
        return row.id


def test_database_runner_persists_sanitized_job(initialized_db):
    run_id = _new_run()

    async def job(_progress):
        return None

    attach_job_spec(
        job,
        "evaluation",
        {"benchmark_id": 1, "judge": {"model": "x", "api_key": "must-not-persist"}},
    )
    asyncio.run(DatabaseJobRunner().submit(run_id, job))

    with session_scope() as session:
        row = session.query(EvaluationJob).one()
        assert row.run_id == run_id
        assert row.status == "queued"
        assert row.payload == {"benchmark_id": 1, "judge": {"model": "x"}}


def test_expired_lease_is_reclaimed(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        session.add(EvaluationJob(run_id=run_id, kind="resume", payload={}, status="queued"))

    first = claim_job("worker-a", 30)
    assert first is not None and first.attempts == 1
    with session_scope() as session:
        row = session.get(EvaluationJob, first.id)
        row.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)

    second = claim_job("worker-b", 30)
    assert second is not None
    assert second.id == first.id
    assert second.attempts == 2
    assert second.lease_owner == "worker-b"


def test_heartbeat_and_graceful_requeue(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        session.add(EvaluationJob(run_id=run_id, kind="resume", payload={}, status="queued"))
    row = claim_job("worker-a", 30)
    assert row is not None
    assert heartbeat_job(row.id, "worker-a", 30, progress={"percent": 25.0})
    assert requeue_job(row.id, "worker-a")
    with session_scope() as session:
        stored = session.get(EvaluationJob, row.id)
        run = session.get(EvalRun, run_id)
        assert stored.status == "queued"
        assert stored.lease_owner is None
        assert run.status == "pending"
        assert run.progress["percent"] == 25.0


def test_worker_restores_last_persisted_progress_floor(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        session.get(EvalRun, run_id).progress = {"percent": 43.9}

    progress = InMemoryProgress()
    _restore_progress_floor(progress, run_id)

    assert progress.snapshot()["percent"] == 43.9


def test_cancelled_job_is_not_reclaimed(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        session.add(EvaluationJob(run_id=run_id, kind="resume", payload={}, status="queued"))
    assert cancel_job(run_id)
    assert claim_job("worker-a", 30) is None


def test_successful_durable_job_atomically_marks_run_success(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        session.add(EvaluationJob(run_id=run_id, kind="evaluation", payload={}, status="queued"))

    job = claim_job("worker-a", 30)
    assert job is not None
    assert finish_job(job.id, "worker-a", "succeeded")

    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        assert run is not None
        assert run.status == "success"
        assert run.error_msg == ""
        assert run.finished_at is not None


def test_reconcile_succeeded_run_status_repairs_only_stale_failure(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        assert run is not None
        run.status = "failed"
        run.error_msg = "评测任务执行失败，详见服务端日志"
        run.finished_at = datetime.utcnow() - timedelta(seconds=10)
        session.add(
            EvaluationJob(
                run_id=run_id,
                kind="evaluation",
                payload={},
                status="succeeded",
                finished_at=datetime.utcnow(),
            )
        )

    assert reconcile_succeeded_run_statuses() == 1
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        assert run is not None
        assert run.status == "success"
        assert run.error_msg == ""


def test_reconcile_succeeded_run_status_does_not_touch_active_run(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        assert run is not None
        run.status = "running"
        session.add(
            EvaluationJob(
                run_id=run_id,
                kind="evaluation",
                payload={},
                status="succeeded",
                finished_at=datetime.utcnow(),
            )
        )

    assert reconcile_succeeded_run_statuses() == 0
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        assert run is not None and run.status == "running"


def test_attribution_job_is_deduplicated_and_can_be_cancelled(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        task = AttributionTask(
            run_id=run_id,
            judge_model_id=1,
            judge_model_name="attribution-model",
            status="queued",
        )
        session.add(task)
        session.flush()
        task_id = task.id

    first = enqueue_attribution_job(run_id, task_id)
    assert enqueue_attribution_job(run_id, task_id) == first
    with session_scope() as session:
        row = session.get(EvaluationJob, first)
        assert row is not None
        assert row.kind == "attribution"
        assert row.payload == {"attribution_task_id": task_id}

    # 归因不改写评测结果，不能阻止用户修复判分异常的 Case。
    assert queue_snapshot(run_id) is None

    assert cancel_attribution_job(task_id)
    with session_scope() as session:
        row = session.get(EvaluationJob, first)
        assert row is not None and row.status == "cancelled"
    assert claim_job("worker-a", 30) is None


def test_execution_job_is_not_deduplicated_against_active_attribution(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        task = AttributionTask(
            run_id=run_id,
            judge_model_id=1,
            judge_model_name="attribution-model",
            status="queued",
        )
        session.add(task)
        session.flush()
        task_id = task.id

    attribution_job_id = enqueue_attribution_job(run_id, task_id)
    retry_job_id = enqueue_job(run_id, "cases_retry", {"sample_ids": ["case_1"]})

    assert retry_job_id != attribution_job_id
    with session_scope() as session:
        rows = list(
            session.query(EvaluationJob)
            .filter(EvaluationJob.run_id == run_id)
            .order_by(EvaluationJob.id)
        )
        assert [(row.kind, row.status) for row in rows] == [
            ("attribution", "queued"),
            ("cases_retry", "queued"),
        ]


def test_cancel_execution_job_does_not_cancel_active_attribution(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        session.add_all(
            [
                EvaluationJob(
                    run_id=run_id,
                    kind="evaluation",
                    payload={},
                    status="queued",
                ),
                EvaluationJob(
                    run_id=run_id,
                    kind="attribution",
                    payload={"attribution_task_id": 99},
                    status="queued",
                ),
            ]
        )

    assert cancel_job(run_id)
    with session_scope() as session:
        rows = list(
            session.query(EvaluationJob)
            .filter(EvaluationJob.run_id == run_id)
            .order_by(EvaluationJob.id)
        )
        assert [(row.kind, row.status) for row in rows] == [
            ("evaluation", "cancelled"),
            ("attribution", "queued"),
        ]


def test_queue_snapshot_keeps_active_evaluation_visible_when_attribution_exists(initialized_db):
    run_id = _new_run()
    with session_scope() as session:
        session.add(EvaluationJob(run_id=run_id, kind="evaluation", payload={}, status="running"))
        session.add(EvaluationJob(run_id=run_id, kind="attribution", payload={}, status="queued"))

    assert queue_snapshot(run_id) == {"state": "running", "position": 0}


def test_interrupted_evaluation_rebuilds_as_in_place_resume(initialized_db):
    settings = initialized_db
    run_id = _new_run()
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        run.run_slug = "durable-slug"
    out_dir = settings.outputs_dir / "durable-slug"
    out_dir.mkdir(parents=True)
    (out_dir / "traces.partial.jsonl").write_text('{"_meta": {}}\n', encoding="utf-8")

    job = build_job_from_payload(
        run_id,
        "evaluation",
        {"benchmark_id": 1, "run_name": "durable", "levels": [], "limit": 0},
        settings,
    )
    spec = get_job_spec(job)
    assert spec is not None
    assert spec.kind == "resume"
    assert spec.payload["source_run_id"] == run_id
    assert spec.payload["in_place"] is True


def test_startup_reconciles_legacy_run_with_checkpoint(initialized_db):
    settings = initialized_db
    run_id = _new_run()
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        run.status = "running"
        run.run_slug = "legacy-running"
    out_dir = settings.outputs_dir / "legacy-running"
    out_dir.mkdir(parents=True)
    (out_dir / "traces.partial.jsonl").write_text('{"_meta": {}}\n', encoding="utf-8")

    assert reconcile_unqueued_runs(settings) == (1, 0)
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        queued = session.query(EvaluationJob).one()
        assert run.status == "pending"
        assert queued.kind == "resume"
        assert queued.payload["in_place"] is True


def test_startup_reconciles_unqueued_case_retry_with_original_scope(initialized_db):
    settings = initialized_db
    run_id = _new_run()
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        run.status = "pending"
        run.run_slug = "orphaned-case-retry"
        run.progress = {
            "context": {
                "kind": "cases_retry",
                "sample_ids": ["case_17", "case_18", "case_17"],
            }
        }
    out_dir = settings.outputs_dir / "orphaned-case-retry"
    out_dir.mkdir(parents=True)
    (out_dir / "report.json").write_text("{}", encoding="utf-8")

    assert reconcile_unqueued_runs(settings) == (1, 0)
    with session_scope() as session:
        queued = session.query(EvaluationJob).one()
        assert queued.kind == "cases_retry"
        assert queued.payload == {"sample_ids": ["case_17", "case_18"]}


def test_startup_reconciles_retry_even_when_attribution_is_active(initialized_db):
    settings = initialized_db
    run_id = _new_run()
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        run.status = "pending"
        run.run_slug = "retry-with-active-attribution"
        run.progress = {
            "context": {"kind": "cases_retry", "sample_ids": ["case_43"]}
        }
        session.add(
            EvaluationJob(
                run_id=run_id,
                kind="attribution",
                payload={"attribution_task_id": 7},
                status="running",
                lease_owner="attribution-worker",
            )
        )
    out_dir = settings.outputs_dir / "retry-with-active-attribution"
    out_dir.mkdir(parents=True)
    (out_dir / "report.json").write_text("{}", encoding="utf-8")

    assert reconcile_unqueued_runs(settings) == (1, 0)
    with session_scope() as session:
        rows = list(
            session.query(EvaluationJob)
            .filter(EvaluationJob.run_id == run_id)
            .order_by(EvaluationJob.id)
        )
        assert [(row.kind, row.status) for row in rows] == [
            ("attribution", "running"),
            ("cases_retry", "queued"),
        ]
