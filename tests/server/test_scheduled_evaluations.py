from datetime import datetime, timezone

from server.models_db import Benchmark, ScheduledEvaluation
from server.services.scheduled_evaluations import compute_next_run_at


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
