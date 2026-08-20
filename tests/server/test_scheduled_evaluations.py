import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from server.models_db import (
    AttributionTask,
    AttributionTaskItem,
    Benchmark,
    CaseResultRow,
    EvalRun,
    JudgeModelConfig,
    ScheduledEvaluation,
)
from server.services.scheduled_evaluations import compute_next_run_at
from server.services.scheduled_evaluations import fetch_latest_active_deeptrace_version_name
from server.services.scheduled_evaluations import run_due_scheduled_evaluations_once


def test_scheduled_evaluation_crud_and_next_run(client, session):
    benchmark = Benchmark(name="定时任务测试集", source="offline")
    session.add(benchmark)
    session.commit()

    payload = {
        "name": "每日回归",
        "benchmark_id": benchmark.id,
        "schedule_kind": "daily",
        "schedule_time": "09:30",
        "evaluation_mode": "single_turn",
        "levels": ["L2"],
        "limit": 0,
        "repeat": 2,
        "enable_rag": True,
        "enable_judge": False,
    }
    response = client.post("/api/scheduled-evaluations", json=payload)
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["enabled"] is True
    assert task["schedule_time"] == "09:30"
    assert task["next_run_at"]

    response = client.patch(f"/api/scheduled-evaluations/{task['id']}", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert client.delete(f"/api/scheduled-evaluations/{task['id']}").status_code == 204


def test_schedule_uses_shanghai_clock_but_stores_utc():
    task = ScheduledEvaluation(schedule_kind="daily", schedule_time="09:30", weekdays=[])
    # 08:00 北京时间（00:00 UTC）时，下一次应是当日 09:30 北京时间（01:30 UTC）。
    assert compute_next_run_at(task, datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc)) == datetime(
        2026, 8, 11, 1, 30
    )


def test_schedule_can_run_immediately_as_a_regression_task(client, session, monkeypatch):
    import asyncio
    from types import SimpleNamespace

    benchmark = Benchmark(name="立即回归测试集", source="offline")
    session.add(benchmark)
    session.commit()
    task = ScheduledEvaluation(
        name="立即回归", benchmark_id=benchmark.id, enable_judge=False, enable_rag=True, repeat=2
    )
    session.add(task)
    session.commit()

    from server.services import scheduled_evaluations as service
    from server.routers import runs

    async def submit(run_id, _job):
        captured["run_id"] = run_id

    def build_job(*_args, **_kwargs):
        async def noop(_progress):
            return None

        return noop

    captured = {}
    monkeypatch.setattr(runs, "build_eval_job", build_job)
    monkeypatch.setattr(service, "get_job_runner", lambda: SimpleNamespace(submit=submit))
    monkeypatch.setattr(service, "fetch_latest_active_deeptrace_version_name", lambda: asyncio.sleep(0, result=None))

    response = client.post(f"/api/scheduled-evaluations/{task.id}/run")
    assert response.status_code == 201, response.text
    run = session.get(EvalRun, response.json()["id"])
    assert run is not None
    assert run.trigger_type == "scheduled"
    assert run.scheduled_evaluation_id == task.id
    assert run.n_runs == 2
    assert run.adapter_overrides["enable_rag"] is True
    assert captured["run_id"] == run.id


def test_streaming_attribution_is_committed_before_job_submission(client, session, monkeypatch):
    """Worker 能看到评测 Job 时，首条 Case 所需的流式归因任务必须已经存在。"""
    from types import SimpleNamespace

    from server.db import session_scope
    from server.routers import runs
    from server.services import scheduled_evaluations as service

    benchmark = Benchmark(name="流式归因原子提交测试集", source="offline")
    judge_model = JudgeModelConfig(
        name="原子提交判分模型", provider="openai", model="judge", api_key="judge-key"
    )
    attribution_model = JudgeModelConfig(
        name="原子提交归因模型", provider="openai", model="attribution", api_key="attr-key"
    )
    session.add_all([benchmark, judge_model, attribution_model])
    session.flush()
    schedule = ScheduledEvaluation(
        name="流式归因原子提交",
        benchmark_id=benchmark.id,
        enable_judge=True,
        judge_model_id=judge_model.id,
        auto_attribution_enabled=True,
        auto_attribution_model_id=attribution_model.id,
    )
    session.add(schedule)
    session.commit()

    async def submit(run_id, _job):
        with session_scope() as verify_session:
            captured["task_id"] = verify_session.scalar(
                select(AttributionTask.id).where(
                    AttributionTask.run_id == run_id,
                    AttributionTask.is_streaming.is_(True),
                )
            )

    def build_job(*_args, **_kwargs):
        async def noop(_progress):
            return None

        return noop

    captured = {}
    monkeypatch.setattr(runs, "build_eval_job", build_job)
    monkeypatch.setattr(service, "get_job_runner", lambda: SimpleNamespace(submit=submit))
    monkeypatch.setattr(
        service,
        "fetch_latest_active_deeptrace_version_name",
        lambda: asyncio.sleep(0, result=None),
    )

    response = client.post(f"/api/scheduled-evaluations/{schedule.id}/run")
    assert response.status_code == 201, response.text
    assert captured["task_id"] is not None


def test_failed_due_schedule_is_retried_after_backoff(session, monkeypatch):
    from server.services import scheduled_evaluations as service

    benchmark = Benchmark(name="失败补偿测试集", source="offline")
    session.add(benchmark)
    session.flush()
    task = ScheduledEvaluation(
        name="失败补偿任务",
        benchmark_id=benchmark.id,
        enabled=True,
        schedule_kind="daily",
        schedule_time="09:00",
        next_run_at=datetime.utcnow() - timedelta(minutes=1),
    )
    session.add(task)
    session.commit()
    task_id = task.id

    async def fail_launch(*_args, **_kwargs):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(service, "launch_scheduled_evaluation", fail_launch)
    before = datetime.utcnow()
    assert asyncio.run(run_due_scheduled_evaluations_once()) == 0

    session.expire_all()
    refreshed = session.get(ScheduledEvaluation, task_id)
    assert "queue unavailable" in refreshed.last_error
    assert before + timedelta(minutes=4, seconds=50) <= refreshed.next_run_at
    assert refreshed.next_run_at <= datetime.utcnow() + timedelta(minutes=5, seconds=10)


def test_scheduled_auto_attribution_only_uses_failed_grade(session, monkeypatch):
    from server.services import attribution_tasks, scheduled_evaluations as service

    benchmark = Benchmark(name="自动归因范围测试集", source="offline")
    model = JudgeModelConfig(
        name="自动归因模型", provider="openai", model="judge", api_key="test-key"
    )
    session.add_all([benchmark, model])
    session.flush()
    schedule = ScheduledEvaluation(
        name="自动归因定时任务",
        benchmark_id=benchmark.id,
        enable_judge=True,
        judge_model_id=model.id,
        auto_attribution_enabled=True,
        auto_attribution_grades=["良好", "不合格"],
        auto_attribution_model_id=model.id,
    )
    session.add(schedule)
    session.flush()
    run = EvalRun(
        run_slug="auto-attribution-run",
        name="自动归因 run",
        status="success",
        trigger_type="scheduled",
        benchmark_id=benchmark.id,
        scheduled_evaluation_id=schedule.id,
    )
    session.add(run)
    session.flush()
    session.add_all([
        CaseResultRow(run_id=run.id, sample_id="good", scenario="x", grade="良好", release_passed=True),
        CaseResultRow(run_id=run.id, sample_id="failed", scenario="x", grade="不合格", release_passed=False),
        CaseResultRow(run_id=run.id, sample_id="pass", scenario="x", grade="合格", release_passed=True),
    ])
    session.commit()
    run_id = run.id

    started: list[int] = []
    monkeypatch.setattr(attribution_tasks, "start_attribution_task", lambda task_id: started.append(task_id))

    assert service.prepare_configured_streaming_attribution(run_id) is None
    task_id = asyncio.run(service.start_configured_attribution(run_id))

    assert task_id is not None
    session.expire_all()
    task = session.get(AttributionTask, task_id)
    assert task is not None
    assert task.requested_count == 1
    assert task.total_count == 1
    assert task.skipped_count == 0
    assert started == [task_id]


def test_scheduled_streaming_attribution_appends_each_failed_case(session, monkeypatch):
    from server.services import attribution_tasks, scheduled_evaluations as service

    benchmark = Benchmark(name="流水线归因测试集", source="offline")
    judge_model = JudgeModelConfig(
        name="判分模型", provider="openai", model="judge", api_key="judge-key"
    )
    attribution_model = JudgeModelConfig(
        name="归因模型", provider="openai", model="attribution", api_key="attribution-key"
    )
    session.add_all([benchmark, judge_model, attribution_model])
    session.flush()
    schedule = ScheduledEvaluation(
        name="流水线归因定时任务",
        benchmark_id=benchmark.id,
        enable_judge=True,
        judge_model_id=judge_model.id,
        auto_attribution_enabled=True,
        auto_attribution_grades=["优秀", "不合格"],
        auto_attribution_model_id=attribution_model.id,
    )
    session.add(schedule)
    session.flush()
    run = EvalRun(
        run_slug="streaming-attribution-run",
        name="流水线归因 run",
        status="running",
        trigger_type="scheduled",
        benchmark_id=benchmark.id,
        scheduled_evaluation_id=schedule.id,
    )
    session.add(run)
    session.commit()

    task_id = service.prepare_configured_streaming_attribution(run.id)
    assert task_id is not None
    task = session.get(AttributionTask, task_id)
    assert task is not None
    assert task.is_streaming is True
    assert task.intake_open is True
    assert task.total_count == 0

    session.add_all([
        CaseResultRow(
            run_id=run.id,
            sample_id="pass",
            scenario="x",
            grade="合格",
            release_passed=True,
        ),
        CaseResultRow(
            run_id=run.id,
            sample_id="failed",
            scenario="x",
            grade="不合格",
            release_passed=False,
        ),
    ])
    session.commit()
    started: list[int] = []
    monkeypatch.setattr(
        attribution_tasks, "start_attribution_task", lambda value: started.append(value)
    )

    assert asyncio.run(
        service.append_configured_streaming_attribution_case(run.id, "pass")
    ) is False
    assert asyncio.run(
        service.append_configured_streaming_attribution_case(run.id, "failed")
    ) is True
    session.expire_all()
    task = session.get(AttributionTask, task_id)
    assert task is not None
    assert task.requested_count == 1
    assert task.total_count == 1
    assert started == [task_id]

    # 重复完成回调必须幂等，不能重复增加同一 Case。
    assert asyncio.run(
        service.append_configured_streaming_attribution_case(run.id, "failed")
    ) is False
    session.expire_all()
    task = session.get(AttributionTask, task_id)
    assert task is not None and task.total_count == 1

    item = session.scalar(
        select(AttributionTaskItem).where(AttributionTaskItem.task_id == task_id)
    )
    assert item is not None
    item.status = "success"
    task.status = "running"
    attribution_tasks._refresh_task_counts(session, task)
    session.commit()
    assert task.status == "running", "接收口未关闭时不能提前完成整批归因任务"

    run.status = "success"
    session.commit()
    assert asyncio.run(service.start_configured_attribution(run.id)) == task_id
    session.expire_all()
    task = session.get(AttributionTask, task_id)
    assert task is not None
    assert task.intake_open is False
    assert task.status == "success"


def test_fetches_latest_active_deeptrace_version_name(settings):
    import asyncio
    from dataclasses import replace
    import httpx

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(
            "http://deeptrace.senzco.com/api/open/v1/spaces/cx/versions?"
        )
        assert str(request.url.params) == "status=active&page=1&pageSize=50"
        assert request.headers["Authorization"] == "Bearer test-deeptrace-token"
        return httpx.Response(200, json={"data": {"items": [{"id": "v2", "name": "0808版本"}]}})

    async def check() -> None:
        configured = replace(settings, deeptrace_open_api_token="test-deeptrace-token")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            name = await fetch_latest_active_deeptrace_version_name(configured, client=client)
        assert name == "0808版本"

    asyncio.run(check())
