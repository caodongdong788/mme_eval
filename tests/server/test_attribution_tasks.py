from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest
from sqlalchemy.exc import IntegrityError

from factories import make_report

from server.db import session_scope
from server.ingest import ingest_report
from server.models_db import (
    AttributionTask,
    AttributionTaskItem,
    CaseResultRow,
    EvalRun,
    JudgeModelConfig,
)
from server.services import attribution_tasks
from server.services.attribution_summary import build_task_diagnostic_summary
from server.services.case_attribution import attribution_input_hash


def _seed_failed_cases() -> tuple[int, list[str], int]:
    report = make_report("batch-attribution")
    for result in report.results:
        result.release_passed = False
    with session_scope() as session:
        run = ingest_report(session, report)
        source = session.query(CaseResultRow).filter_by(run_id=run.id).first()
        assert source is not None
        extra_ids = []
        for index in range(3):
            sample_id = f"batch_case_{index + 1}"
            extra_ids.append(sample_id)
            session.add(CaseResultRow(
                run_id=run.id,
                sample_id=sample_id,
                scenario=source.scenario,
                case_type=source.case_type,
                sub_scenario=source.sub_scenario,
                level=source.level,
                source=source.source,
                tags=deepcopy(source.tags),
                medical_safety_passed=False,
                release_passed=False,
                composite_score=source.composite_score,
                guideline_earned=source.guideline_earned,
                guideline_max=source.guideline_max,
                grade="不合格",
                stability=source.stability,
                n_turns=source.n_turns,
                rag_status=source.rag_status,
                failure_tags=deepcopy(source.failure_tags),
                detail_json=deepcopy(source.detail_json),
            ))
        model = session.query(JudgeModelConfig).first()
        if model is None:
            model = JudgeModelConfig(
                name="batch-attribution-model",
                provider="openai",
                model="fake-model",
                base_url="https://example.test/v1",
                temperature=0.0,
                enable_thinking=False,
                api_key="test-key",
            )
            session.add(model)
            session.flush()
        return run.id, [source.sample_id, *extra_ids], model.id


def test_task_diagnostic_summary_clusters_same_root_cause_across_cases():
    def stored(sample: str, dimension: str, severity: str):
        return {
            "available": True,
            "analysis": {
                "score_health": {"status": "healthy", "issues": []},
                "deduction_analyses": [
                    {
                        "deduction_id": f"guideline.{sample}",
                        "dimension": dimension,
                        "severity": severity,
                        "deduction_validation": "supported",
                        "finding": "已召回正确证据但回答没有使用",
                        "primary_cause": {
                            "code": "rag_not_grounded",
                            "label": "召回证据未用于回答",
                            "owner": "generator",
                            "confidence": 0.9,
                        },
                        "recommendations": [
                            {
                                "priority": "P1",
                                "target": "提示词优化",
                                "action": "回答前逐条核对选中文献",
                                "verification": "重跑目标用例",
                            }
                        ],
                    }
                ],
                "global_recommendations": [
                    {
                        "priority": "P0",
                        "target": "判分模型",
                        "action": "调整判分提示词",
                        "verification": "重新判分",
                    },
                    {
                        "priority": "P1",
                        "target": "回答生成",
                        "action": "生成前检查证据覆盖",
                        "verification": "重跑目标用例",
                    },
                ],
                "verification_plan": {
                    "control_cases": ["同 Rubric 通过用例"],
                    "safety_checks": ["医学安全不得回退"],
                    "acceptance_criteria": ["目标扣分不再出现"],
                },
            },
        }

    summary = build_task_diagnostic_summary(
        [
            ("case_1", stored("g01", "professional_accuracy", "high")),
            ("case_2", stored("g02", "clinical_inquiry", "medium")),
        ]
    )

    assert summary["available_results"] == 2
    assert summary["validation_counts"] == {"supported": 2}
    assert len(summary["clusters"]) == 1
    cluster = summary["clusters"][0]
    assert cluster["case_count"] == 2
    assert cluster["deduction_count"] == 2
    assert cluster["dimensions"] == ["professional_accuracy", "clinical_inquiry"]
    assert cluster["verification_plan"]["acceptance_criteria"] == ["目标扣分不再出现"]
    assert all(item["target"] != "判分模型" for item in cluster["recommendations"])


def test_task_diagnostic_summary_does_not_merge_different_business_causes():
    def stored(label: str):
        return {
            "analysis": {
                "score_health": {"status": "healthy"},
                "deduction_analyses": [
                    {
                        "deduction_id": f"guideline.{label}",
                        "dimension": "professional_accuracy",
                        "severity": "high",
                        "deduction_validation": "supported",
                        "issue_type": "factual_error",
                        "root_cause_stage": "generation",
                        "finding": label,
                        "primary_cause": {
                            "code": "reasoning_error",
                            "label": label,
                            "owner": "generator",
                            "confidence": 0.9,
                        },
                    }
                ],
            }
        }

    summary = build_task_diagnostic_summary(
        [("case_1", stored("药物剂量推理错误")), ("case_2", stored("检查时机推理错误"))]
    )

    assert len(summary["clusters"]) == 2


def test_batch_attribution_runs_three_cases_concurrently_and_persists_items(
    initialized_db, monkeypatch
):
    run_id, sample_ids, model_id = _seed_failed_cases()
    active = 0
    max_active = 0

    async def fake_generate(
        session,
        run,
        row,
        *,
        settings=None,
        judge_model_id=None,
        attribution_task_id=None,
        attribution_item_id=None,
    ):
        nonlocal active, max_active
        assert judge_model_id == model_id
        assert attribution_task_id is not None
        assert attribution_item_id is not None
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        detail = dict(row.detail_json or {})
        detail["attribution_analysis"] = {
            "analysis": {"analysis_status": "complete", "deduction_analyses": []},
            "metadata": {"input_hash": attribution_input_hash(detail)},
        }
        row.detail_json = detail
        return {"available": True, "stale": False, "analysis": detail["attribution_analysis"]["analysis"], "metadata": detail["attribution_analysis"]["metadata"]}

    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)
    monkeypatch.setattr(attribution_tasks, "generate_case_attribution", fake_generate)
    monkeypatch.setattr(attribution_tasks, "_global_semaphore", None)

    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        task = attribution_tasks.create_attribution_task(
            session,
            run,
            sample_ids=sample_ids,
            judge_model_id=model_id,
            created_by="test",
        )
        task_id = task.id

    asyncio.run(attribution_tasks.run_attribution_task(task_id))

    with session_scope() as session:
        payload = attribution_tasks.get_attribution_task(session, run_id, task_id)
    assert max_active == 3
    assert payload["status"] == "success"
    assert payload["completed_count"] == 4
    assert payload["success_count"] == 4
    assert all(item["attribution_available"] for item in payload["items"])


def test_batch_attribution_skips_passed_cases(initialized_db, monkeypatch):
    run_id, sample_ids, model_id = _seed_failed_cases()
    with session_scope() as session:
        first = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id=sample_ids[0]).one()
        first.release_passed = True
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        task = attribution_tasks.create_attribution_task(
            session, run, sample_ids=sample_ids, judge_model_id=model_id, created_by="test"
        )
        assert task.requested_count == 4
        assert task.total_count == 3
        assert task.skipped_count == 1


def test_database_rejects_two_active_attribution_tasks_for_same_run(
    initialized_db, monkeypatch
):
    run_id, sample_ids, model_id = _seed_failed_cases()
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        attribution_tasks.create_attribution_task(
            session, run, sample_ids=sample_ids, judge_model_id=model_id, created_by="test"
        )
        session.add(
            AttributionTask(
                run_id=run_id,
                judge_model_id=model_id,
                judge_model_name="duplicate",
                status="queued",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_batch_attribution_api_creates_task_and_returns_pending_items(client, monkeypatch):
    run_id, sample_ids, model_id = _seed_failed_cases()
    started: list[int] = []
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)
    monkeypatch.setattr(attribution_tasks, "start_attribution_task", lambda task_id: started.append(task_id))

    response = client.post(
        f"/api/runs/{run_id}/attribution-tasks",
        json={"sample_ids": sample_ids, "judge_model_id": model_id},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["total_count"] == 4
    assert payload["running_count"] == 0
    assert payload["pending_count"] == 4
    assert [item["status"] for item in payload["items"]] == ["pending"] * 4
    assert started == [payload["id"]]
    listed = client.get(f"/api/runs/{run_id}/attribution-tasks")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == payload["id"]


def test_batch_attribution_api_starts_task_from_async_request_loop(client, monkeypatch):
    run_id, sample_ids, model_id = _seed_failed_cases()
    started: list[int] = []
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)

    def fake_start(task_id: int) -> None:
        asyncio.get_running_loop()
        started.append(task_id)

    monkeypatch.setattr(attribution_tasks, "start_attribution_task", fake_start)
    response = client.post(
        f"/api/runs/{run_id}/attribution-tasks",
        json={"sample_ids": sample_ids, "judge_model_id": model_id},
    )

    assert response.status_code == 201, response.text
    assert started == [response.json()["id"]]


def test_failed_task_start_releases_active_task_lock(initialized_db, monkeypatch):
    run_id, sample_ids, model_id = _seed_failed_cases()
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        task = attribution_tasks.create_attribution_task(
            session, run, sample_ids=sample_ids, judge_model_id=model_id, created_by="test"
        )
        task_id = task.id

    attribution_tasks.mark_attribution_task_start_failed(task_id, RuntimeError("no loop"))

    with session_scope() as session:
        failed = attribution_tasks.get_attribution_task(session, run_id, task_id)
        assert failed["status"] == "failed"
        run = session.get(EvalRun, run_id)
        replacement = attribution_tasks.create_attribution_task(
            session, run, sample_ids=sample_ids, judge_model_id=model_id, created_by="test"
        )
        assert replacement.id != task_id


def test_all_case_failures_mark_whole_task_failed(initialized_db, monkeypatch):
    run_id, sample_ids, model_id = _seed_failed_cases()
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)

    async def fail_generate(*_args, **_kwargs):
        raise RuntimeError("model rejected request")

    monkeypatch.setattr(attribution_tasks, "generate_case_attribution", fail_generate)
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        task = attribution_tasks.create_attribution_task(
            session, run, sample_ids=sample_ids, judge_model_id=model_id, created_by="test"
        )
        task_id = task.id

    asyncio.run(attribution_tasks.run_attribution_task(task_id))
    with session_scope() as session:
        payload = attribution_tasks.get_attribution_task(session, run_id, task_id)
    assert payload["status"] == "failed"
    assert payload["success_count"] == 0
    assert payload["failed_count"] == len(sample_ids)


def test_each_attribution_task_keeps_its_own_result_snapshot(initialized_db, monkeypatch):
    run_id, sample_ids, model_id = _seed_failed_cases()
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)

    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        first = attribution_tasks.create_attribution_task(
            session,
            run,
            sample_ids=[sample_ids[0]],
            judge_model_id=model_id,
            created_by="test",
        )
        first_item = session.query(AttributionTaskItem).filter_by(task_id=first.id).one()
        first_item.analysis_json = {
            "available": True,
            "stale": False,
            "analysis": {"overall": {"summary": "第一次归因"}},
            "metadata": {},
        }
        first_item.status = "success"
        first.status = "success"
        first.completed_count = 1
        first.success_count = 1
        first_id = first.id

    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        second = attribution_tasks.create_attribution_task(
            session,
            run,
            sample_ids=[sample_ids[0]],
            judge_model_id=model_id,
            created_by="test",
        )
        second_item = session.query(AttributionTaskItem).filter_by(task_id=second.id).one()
        second_item.analysis_json = {
            "available": True,
            "stale": False,
            "analysis": {"overall": {"summary": "第二次归因"}},
            "metadata": {},
        }
        second_item.status = "success"
        second.status = "success"
        second.completed_count = 1
        second.success_count = 1
        second_id = second.id

    with session_scope() as session:
        first_result = attribution_tasks.get_attribution_task_item_result(
            session, run_id, first_id, sample_ids[0]
        )
        second_result = attribution_tasks.get_attribution_task_item_result(
            session, run_id, second_id, sample_ids[0]
        )

    assert first_result["analysis"]["overall"]["summary"] == "第一次归因"
    assert second_result["analysis"]["overall"]["summary"] == "第二次归因"


def test_attribution_task_api_reruns_selected_items_in_place_and_deletes(client, monkeypatch):
    run_id, sample_ids, model_id = _seed_failed_cases()
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)
    monkeypatch.setattr(attribution_tasks, "start_attribution_task", lambda _task_id: None)

    created = client.post(
        f"/api/runs/{run_id}/attribution-tasks",
        json={"sample_ids": sample_ids, "judge_model_id": model_id},
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]
    attribution_tasks.mark_attribution_task_start_failed(source_id, RuntimeError("test stop"))

    rerun = client.post(
        f"/api/runs/{run_id}/attribution-tasks/{source_id}/rerun",
        json={"sample_ids": [sample_ids[0]]},
    )
    assert rerun.status_code == 200, rerun.text
    rerun_id = rerun.json()["id"]
    assert rerun_id == source_id
    assert rerun.json()["total_count"] == len(sample_ids)
    items = {item["sample_id"]: item for item in rerun.json()["items"]}
    assert items[sample_ids[0]]["status"] == "pending"
    assert items[sample_ids[0]]["attempt_count"] == 1
    assert items[sample_ids[1]]["status"] == "failed"
    assert items[sample_ids[1]]["attempt_count"] == 0

    deleted = client.delete(f"/api/runs/{run_id}/attribution-tasks/{rerun_id}")
    assert deleted.status_code == 204, deleted.text
    missing = client.get(f"/api/runs/{run_id}/attribution-tasks/{rerun_id}")
    assert missing.status_code == 404


def test_deleting_run_cascades_attribution_task_and_items(client, monkeypatch):
    run_id, sample_ids, model_id = _seed_failed_cases()
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)
    monkeypatch.setattr(attribution_tasks, "start_attribution_task", lambda _task_id: None)

    created = client.post(
        f"/api/runs/{run_id}/attribution-tasks",
        json={"sample_ids": sample_ids, "judge_model_id": model_id},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    deleted = client.delete(f"/api/runs/{run_id}")
    assert deleted.status_code == 204, deleted.text

    with session_scope() as session:
        assert session.get(EvalRun, run_id) is None
        assert session.get(AttributionTask, task_id) is None
        assert session.query(AttributionTaskItem).filter_by(task_id=task_id).count() == 0


def test_attribution_task_api_resumes_only_unfinished_items(client, monkeypatch):
    run_id, sample_ids, model_id = _seed_failed_cases()
    started: list[int] = []
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)
    monkeypatch.setattr(attribution_tasks, "start_attribution_task", lambda task_id: started.append(task_id))

    created = client.post(
        f"/api/runs/{run_id}/attribution-tasks",
        json={"sample_ids": sample_ids, "judge_model_id": model_id},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    # 模拟服务中断：第一条已成功且有快照，其他用例未完成/失败。
    with session_scope() as session:
        task = attribution_tasks.get_attribution_task_or_404(session, run_id, task_id)
        items = list(session.query(AttributionTaskItem).filter_by(task_id=task_id).order_by(AttributionTaskItem.id))
        items[0].status = "success"
        items[0].analysis_json = {"available": True, "analysis": {"overall": {"summary": "保留"}}}
        for item in items[1:]:
            item.status = "failed"
            item.error_msg = "服务重启导致归因中断"
        attribution_tasks._refresh_task_counts(session, task)

    resumed = client.post(f"/api/runs/{run_id}/attribution-tasks/{task_id}/resume")
    assert resumed.status_code == 200, resumed.text
    payload = resumed.json()
    assert payload["id"] == task_id
    assert payload["status"] == "queued"
    assert payload["success_count"] == 1
    assert payload["completed_count"] == 1
    assert payload["pending_count"] == len(sample_ids) - 1
    assert payload["items"][0]["status"] == "success"
    assert payload["items"][0]["attribution_available"] is True
    assert {item["status"] for item in payload["items"][1:]} == {"pending"}
    assert started == [task_id, task_id]


def test_resumed_task_executes_only_pending_items(initialized_db, monkeypatch):
    run_id, sample_ids, model_id = _seed_failed_cases()
    monkeypatch.setattr(attribution_tasks, "has_judge_model_api_key", lambda _model: True)
    called: list[str] = []

    async def fake_generate(_session, _run, row, **_kwargs):
        called.append(row.sample_id)
        return {"available": True, "stale": False, "analysis": {}, "metadata": {}}

    monkeypatch.setattr(attribution_tasks, "generate_case_attribution", fake_generate)
    monkeypatch.setattr(attribution_tasks, "_global_semaphore", None)
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        task = attribution_tasks.create_attribution_task(
            session, run, sample_ids=sample_ids, judge_model_id=model_id, created_by="test"
        )
        items = list(session.query(AttributionTaskItem).filter_by(task_id=task.id).order_by(AttributionTaskItem.id))
        items[0].status = "success"
        items[0].analysis_json = {"available": True, "analysis": {}}
        for item in items[1:]:
            item.status = "failed"
        attribution_tasks._refresh_task_counts(session, task)
        task_id = task.id
        attribution_tasks.resume_attribution_task(session, run_id, task_id)

    asyncio.run(attribution_tasks.run_attribution_task(task_id))
    assert set(called) == set(sample_ids[1:])
    assert sample_ids[0] not in called
