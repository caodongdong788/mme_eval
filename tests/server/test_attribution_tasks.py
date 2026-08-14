from __future__ import annotations

import asyncio
from copy import deepcopy

from factories import make_report

from server.db import session_scope
from server.ingest import ingest_report
from server.models_db import AttributionTaskItem, CaseResultRow, EvalRun, JudgeModelConfig
from server.services import attribution_tasks
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


def test_attribution_task_api_supports_rerun_and_delete(client, monkeypatch):
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

    rerun = client.post(f"/api/runs/{run_id}/attribution-tasks/{source_id}/rerun")
    assert rerun.status_code == 201, rerun.text
    rerun_id = rerun.json()["id"]
    assert rerun_id != source_id
    assert rerun.json()["total_count"] == len(sample_ids)

    deleted = client.delete(f"/api/runs/{run_id}/attribution-tasks/{rerun_id}")
    assert deleted.status_code == 204, deleted.text
    missing = client.get(f"/api/runs/{run_id}/attribution-tasks/{rerun_id}")
    assert missing.status_code == 404


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
