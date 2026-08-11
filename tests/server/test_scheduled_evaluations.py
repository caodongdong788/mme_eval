from datetime import datetime, timezone

from server.models_db import Benchmark, ScheduledEvaluation
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


def test_fetches_latest_active_deeptrace_version_name(settings):
    import asyncio
    from dataclasses import replace
    import httpx

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(
            "http://deeptrace.senzco.com/api/open/v1/spaces/space-cx/versions?"
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
