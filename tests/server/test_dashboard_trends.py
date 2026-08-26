"""趋势看板聚合：定时回归任务必须只查看自身的历次运行。"""

from server.models_db import Benchmark, EvalRun, ScheduledEvaluation


def _run(*, name: str, task_id: int | None, trigger_type: str = "scheduled") -> EvalRun:
    return EvalRun(
        run_slug=name,
        name=name,
        status="success",
        trigger_type=trigger_type,
        scheduled_evaluation_id=task_id,
        total=10,
        passed=8,
        pass_rate=0.8,
        medical_safety_failed=1,
        grading={
            "avg_composite": 32.5,
            "avg_dimension": {"medical_safety": 4.5},
            "reliability": {"pass_at_k": 0.9, "pass_all_k": 0.8, "flaky_cases": 1},
        },
        latency_summary={"avg_ms": 1200, "p90_ms": 1500},
        ttft_summary={"avg_ms": 200},
        token_summary={"total_tokens": 3000, "avg_tokens_per_run": 300},
        by_case_type={"检查报告": {"total": 10, "passed": 8}},
    )


def test_regression_trends_are_scoped_to_one_scheduled_task(client, session):
    benchmark = Benchmark(name="回归看板测试集", source="offline")
    session.add(benchmark)
    session.flush()
    task_a = ScheduledEvaluation(name="每日回归 A", benchmark_id=benchmark.id)
    task_b = ScheduledEvaluation(name="每日回归 B", benchmark_id=benchmark.id)
    session.add_all([task_a, task_b])
    session.flush()
    session.add_all(
        [
            _run(name="每日回归 A · 定时 1", task_id=task_a.id),
            _run(name="每日回归 A · 定时 2", task_id=task_a.id),
            _run(name="每日回归 B · 定时 1", task_id=task_b.id),
            _run(name="人工运行", task_id=None, trigger_type="manual"),
        ]
    )
    session.commit()

    response = client.get("/api/dashboard/regression-trends", params={"scheduled_evaluation_id": task_a.id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scheduled_evaluation"] == {
        "id": task_a.id,
        "name": "每日回归 A",
        "benchmark_id": benchmark.id,
    }
    assert [point["name"] for point in body["points"]] == ["每日回归 A · 定时 1", "每日回归 A · 定时 2"]
    assert body["points"][0]["avg_dimension"] == {"medical_safety": 4.5}
    assert body["points"][0]["latency_summary"]["p90_ms"] == 1500
    assert body["points"][0]["token_summary"]["total_tokens"] == 3000
    assert body["points"][0]["reliability"]["pass_at_k"] == 0.9
    assert body["points"][0]["by_case_type"]["检查报告"]["passed"] == 8


def test_runs_metrics_only_aggregates_completed_runs_and_sorts_failure_rate(client, session):
    benchmark = Benchmark(name="列表汇总测试集", source="offline")
    session.add(benchmark)
    session.flush()
    first = _run(name="汇总运行 1", task_id=None, trigger_type="manual")
    first.grading["avg_dimension"] = {
        "medical_safety": 4.0,
        "professional_accuracy": 3.0,
    }
    first.by_case_type = {
        "检查报告": {"total": 10, "passed": 9},
        "用药安全": {"total": 2, "passed": 0},
    }
    second = _run(name="汇总运行 2", task_id=None, trigger_type="manual")
    second.total = 20
    second.grading["avg_dimension"] = {
        "medical_safety": 3.0,
        "professional_accuracy": 4.0,
    }
    second.by_case_type = {
        "检查报告": {"total": 20, "passed": 10},
        "用药安全": {"total": 2, "passed": 1},
    }
    ignored = _run(name="失败运行", task_id=None, trigger_type="manual")
    ignored.status = "failed"
    ignored.grading["avg_dimension"] = {"medical_safety": 0.0}
    session.add_all([first, second, ignored])
    session.commit()

    response = client.post("/api/dashboard/runs/metrics", json={"run_ids": [first.id, second.id, ignored.id]})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["completed_run_count"] == 2
    dimensions = {item["key"]: item for item in body["dimension_averages"]}
    assert dimensions["medical_safety"]["label"] == "医学安全性"
    assert dimensions["medical_safety"]["average"] == 3.333
    assert dimensions["professional_accuracy"]["average"] == 3.667
    assert dimensions["clinical_inquiry"]["average"] is None
    assert body["case_type_failure_rates"] == [
        {"case_type": "用药安全", "total": 4, "passed": 1, "failed": 3, "failure_rate": 75.0},
        {"case_type": "检查报告", "total": 30, "passed": 19, "failed": 11, "failure_rate": 36.7},
    ]
