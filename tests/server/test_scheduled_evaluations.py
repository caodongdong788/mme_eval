from datetime import datetime, timezone

from server.models_db import Benchmark, EvalRun, ScheduledEvaluation
from server.services.scheduled_evaluations import compute_next_run_at
from server.services.scheduled_evaluations import fetch_latest_active_deeptrace_version_name


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
