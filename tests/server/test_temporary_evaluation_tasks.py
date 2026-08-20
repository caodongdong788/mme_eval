"""临时评测异步任务：幂等、永久落库、每日 Run 汇总与租约恢复。"""

from __future__ import annotations

from datetime import datetime, timedelta
import time

from fastapi import HTTPException

from server.models_db import EvalRun, TemporaryEvaluation


def _create_key(client, name: str) -> tuple[dict[str, str], int]:
    response = client.post(
        "/api/config/open-api-keys",
        json={
            "name": name,
            "permissions": ["temporary_evaluations:create"],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"X-MME-API-Key": body["api_key"]}, body["id"]


def test_temporary_evaluation_is_idempotent_and_scoped_to_api_key(
    client, session, monkeypatch
):
    from server.services import temporary_evaluation
    from server.services import temporary_evaluation_tasks as tasks

    monkeypatch.setattr(temporary_evaluation, "_platform_benchmarks", lambda _session: [])
    monkeypatch.setattr(tasks, "schedule_temporary_evaluation", lambda _evaluation_id: None)
    first_headers, first_key_id = _create_key(client, "临时评测 Key A")
    second_headers, _second_key_id = _create_key(client, "临时评测 Key B")
    payload = {
        "external_request_id": "local-validation-001",
        "question": "最近总是睡不好怎么办？",
        "answer": "先记录一周睡眠情况，再逐步调整作息。",
    }

    first = client.post(
        "/api/open/v1/temporary-evaluations", headers=first_headers, json=payload
    )
    repeated = client.post(
        "/api/open/v1/temporary-evaluations", headers=first_headers, json=payload
    )

    assert first.status_code == repeated.status_code == 202
    assert first.json()["evaluation_id"] == repeated.json()["evaluation_id"]
    assert session.query(TemporaryEvaluation).count() == 1
    row = session.query(TemporaryEvaluation).one()
    assert row.api_key_id == first_key_id
    assert row.status == "pending"
    assert row.expires_at is None
    assert row.run_id is not None
    run = session.get(EvalRun, row.run_id)
    assert run is not None
    assert run.trigger_type == "open_api"
    assert run.name.endswith("临时评测")
    assert run.total == 1

    status = client.get(first.json()["status_url"], headers=first_headers)
    assert status.status_code == 200
    assert status.json()["status"] == "pending"
    assert status.json()["result"] is None
    assert status.json()["retry_after_seconds"] == 5

    hidden = client.get(first.json()["status_url"], headers=second_headers)
    assert hidden.status_code == 404

    conflict = client.post(
        "/api/open/v1/temporary-evaluations",
        headers=first_headers,
        json={**payload, "answer": "这是另一份回答。"},
    )
    assert conflict.status_code == 409
    assert "external_request_id" in conflict.json()["detail"]


def test_temporary_evaluation_lease_can_be_reclaimed(client, session, monkeypatch):
    from server.services import temporary_evaluation
    from server.services import temporary_evaluation_tasks as tasks

    monkeypatch.setattr(temporary_evaluation, "_platform_benchmarks", lambda _session: [])
    monkeypatch.setattr(tasks, "schedule_temporary_evaluation", lambda _evaluation_id: None)
    headers, _key_id = _create_key(client, "临时评测租约 Key")
    created = client.post(
        "/api/open/v1/temporary-evaluations",
        headers=headers,
        json={"question": "问题", "answer": "回答"},
    ).json()

    first = tasks.claim_temporary_evaluation("worker-a", 30)
    assert first is not None
    assert first.evaluation_id == created["evaluation_id"]
    assert first.attempts == 1
    assert tasks.heartbeat_temporary_evaluation(first.evaluation_id, "worker-a", 30)
    assert tasks.requeue_temporary_evaluation(first.evaluation_id, "worker-a")

    second = tasks.claim_temporary_evaluation("worker-b", 30)
    assert second is not None
    assert second.evaluation_id == first.evaluation_id
    assert second.attempts == 2
    assert second.lease_owner == "worker-b"


def test_temporary_evaluation_failure_is_queryable(client, monkeypatch):
    from server.services import temporary_evaluation

    monkeypatch.setattr(temporary_evaluation, "_platform_benchmarks", lambda _session: [])
    monkeypatch.setattr(temporary_evaluation, "build_judge_stack", lambda _config: [])

    async def fail_judge(*_args, **_kwargs):
        raise HTTPException(status_code=502, detail="判分模型暂时不可用")

    monkeypatch.setattr(temporary_evaluation, "judge_all", fail_judge)
    headers, _key_id = _create_key(client, "临时评测失败 Key")
    created = client.post(
        "/api/open/v1/temporary-evaluations",
        headers=headers,
        json={"question": "问题", "answer": "回答"},
    )
    assert created.status_code == 202

    status = None
    for _ in range(100):
        response = client.get(created.json()["status_url"], headers=headers)
        assert response.status_code == 200
        status = response.json()
        if status["status"] in {"success", "failed"}:
            break
        time.sleep(0.01)

    assert status is not None and status["status"] == "failed"
    assert status["result"] is None
    assert status["error"] == {
        "code": "judge_evaluation_failed",
        "message": "判分模型暂时不可用",
        "retryable": True,
    }
    assert status["retry_after_seconds"] is None


def test_temporary_evaluations_are_not_deleted_after_legacy_expiry(
    client, session, monkeypatch
):
    from server.services import temporary_evaluation
    from server.services import temporary_evaluation_tasks as tasks

    monkeypatch.setattr(temporary_evaluation, "_platform_benchmarks", lambda _session: [])
    monkeypatch.setattr(tasks, "schedule_temporary_evaluation", lambda _evaluation_id: None)
    headers, _key_id = _create_key(client, "临时评测清理 Key")
    created = client.post(
        "/api/open/v1/temporary-evaluations",
        headers=headers,
        json={"question": "问题", "answer": "回答"},
    ).json()
    row = session.query(TemporaryEvaluation).one()
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    session.commit()

    assert tasks.cleanup_expired_temporary_evaluations() == 0
    session.expire_all()
    assert session.query(TemporaryEvaluation).count() == 1
    retained = client.get(created["status_url"], headers=headers)
    assert retained.status_code == 200
    assert retained.json()["status"] == "pending"


def test_same_day_temporary_evaluations_share_one_open_api_run(client, session, monkeypatch):
    from server.services import temporary_evaluation
    from server.services import temporary_evaluation_tasks as tasks

    monkeypatch.setattr(temporary_evaluation, "_platform_benchmarks", lambda _session: [])
    monkeypatch.setattr(tasks, "schedule_temporary_evaluation", lambda _evaluation_id: None)
    headers, _key_id = _create_key(client, "临时评测每日汇总 Key")
    for index in (1, 2):
        response = client.post(
            "/api/open/v1/temporary-evaluations",
            headers=headers,
            json={
                "external_request_id": f"daily-group-{index}",
                "question": f"问题 {index}",
                "answer": f"回答 {index}",
            },
        )
        assert response.status_code == 202, response.text

    rows = session.query(TemporaryEvaluation).order_by(TemporaryEvaluation.id).all()
    assert len(rows) == 2
    assert rows[0].run_id == rows[1].run_id
    assert session.query(EvalRun).count() == 1
    assert session.get(EvalRun, rows[0].run_id).total == 2
