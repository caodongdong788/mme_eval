"""DeepTrace Agent 自动化结果回写。"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime
import json

import httpx

from server.models_db import CaseResultRow, EvalRun
from server.services.deeptrace_automation import report_run_completion


def _case(run_id: int, sample_id: str, *, passed: bool) -> CaseResultRow:
    return CaseResultRow(
        run_id=run_id,
        sample_id=sample_id,
        release_passed=passed,
        medical_safety_passed=passed,
        composite_score=30.0,
        guideline_earned=0.0,
        guideline_max=0.0,
    )


def test_reports_open_api_run_completion_to_existing_deeptrace_execution(session, settings):
    run = EvalRun(
        run_slug="deeptrace-agent",
        name="Agent 自动化评测",
        status="success",
        trigger_type="open_api",
        finished_at=datetime(2026, 8, 21, 8, 55),
        adapter_overrides={"deeptrace": {"execution_id": "agent-jenkins-354"}},
    )
    session.add(run)
    session.flush()
    session.add_all([
        _case(run.id, "case_1", passed=True),
        _case(run.id, "case_2", passed=True),
        _case(run.id, "case_3", passed=False),
    ])
    session.commit()

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": {"executionId": "agent-jenkins-354"}})

    configured = replace(
        settings,
        deeptrace_base_url="https://deeptrace.test",
        deeptrace_space_key="CX",
        deeptrace_open_api_token="deeptrace-test-token",
        frontend_url="https://mme.test",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        reported = asyncio.run(report_run_completion(run.id, configured, client=client))
    finally:
        asyncio.run(client.aclose())

    assert reported is True
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "PATCH"
    assert str(request.url) == (
        "https://deeptrace.test/api/open/v1/spaces/CX/automation-test-runs/agent-jenkins-354"
    )
    assert request.headers["authorization"] == "Bearer deeptrace-test-token"
    assert json.loads(request.content) == {
        "totalCases": 3,
        "passedCases": 2,
        "failedCases": 1,
        "bugsFound": 0,
        "reportUrl": f"https://mme.test/runs/{run.id}",
        "executedAt": "2026-08-21T16:55:00+08:00",
    }
    session.expire_all()
    stored = session.get(EvalRun, run.id)
    assert stored.adapter_overrides["deeptrace"]["last_sync_status"] == "success"
    assert stored.adapter_overrides["deeptrace"]["last_error"] == ""


def test_does_not_call_deeptrace_without_server_token(session, settings):
    run = EvalRun(
        run_slug="deeptrace-unconfigured",
        name="Agent 自动化评测",
        status="success",
        trigger_type="open_api",
        adapter_overrides={"deeptrace": {"execution_id": "agent-jenkins-355"}},
    )
    session.add(run)
    session.commit()

    assert asyncio.run(report_run_completion(run.id, settings)) is False
    session.expire_all()
    stored = session.get(EvalRun, run.id)
    assert stored.adapter_overrides["deeptrace"]["last_sync_status"] == "skipped"
