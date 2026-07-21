"""用例明细暴露 Langfuse 深链：cases 列表带 langfuse_trace_url；缺失安全回退 None。"""

from __future__ import annotations

from factories import make_case_result, make_report

from medeval.models import ChatMessage, ConversationTrace
from server.db import session_scope
from server.ingest import ingest_report
from server.models_db import Benchmark, CaseResultRow
from server.settings import Settings


def _result_with_trace_url(sample_id: str, url: str | None):
    base = make_case_result(sample_id)
    base.trace = ConversationTrace(
        messages=[
            ChatMessage(role="user", content="问"),
            ChatMessage(role="assistant", content="答"),
        ],
        duration_ms=100,
        langfuse_trace_url=url,
    )
    return base


def _seed(settings) -> int:
    with session_scope() as s:
        bm = Benchmark(
            name="langfuse-v2",
            source="uploaded",
            storage_path="cases/benchmark",
            case_count=2,
        )
        s.add(bm)
        s.flush()
        report = make_report("lf_run")
        report.results = [
            _result_with_trace_url("bc_with", "https://lf.example/trace/abc"),
            _result_with_trace_url("bc_without", None),
        ]
        report.total = len(report.results)
        run = ingest_report(s, report, benchmark_id=bm.id)
        s.flush()
        return run.id


def test_cases_list_omits_langfuse_trace_url(client, settings):
    """列表路径不加载 detail_json，langfuse 深链仅在用例明细返回。"""
    rid = _seed(settings)
    rows = client.get(f"/api/runs/{rid}/cases").json()
    by = {r["sample_id"]: r for r in rows}
    assert by["bc_with"]["langfuse_trace_url"] is None
    assert by["bc_without"]["langfuse_trace_url"] is None


def test_case_detail_includes_trace_url(client, settings):
    rid = _seed(settings)
    detail = client.get(f"/api/runs/{rid}/cases/bc_with").json()
    assert detail["trace"]["langfuse_trace_url"] == "https://lf.example/trace/abc"


def test_case_detail_exposes_login_account_and_verification_code_for_existing_result(
    client, settings, monkeypatch
):
    rid = _seed(settings)
    monkeypatch.setenv(
        "CX_AGENT_EVALUATION_LOGIN_CODES",
        "+8610000000101=731904",
    )
    with session_scope() as session:
        row = session.query(CaseResultRow).filter_by(run_id=rid, sample_id="bc_with").one()
        detail = dict(row.detail_json)
        detail["trace"] = {
            **detail["trace"],
            "evaluation_identity": {
                "test_user_id": "00000000-0000-0000-0000-000000000101"
            },
        }
        row.detail_json = detail

    identity = client.get(f"/api/runs/{rid}/cases/bc_with").json()["trace"][
        "evaluation_identity"
    ]
    assert identity["login_account"] == "+8610000000101"
    assert identity["verification_code"] == "731904"


def test_case_agent_chain_sync_persists_fail_soft_snapshot(
    client, settings, monkeypatch
):
    rid = _seed(settings)
    with session_scope() as session:
        row = session.query(CaseResultRow).filter_by(run_id=rid, sample_id="bc_with").one()
        detail = dict(row.detail_json)
        detail["trace"] = {
            **detail["trace"],
            "langfuse_trace_ids": ["cx-trace-1"],
        }
        row.detail_json = detail

    monkeypatch.setattr(
        "server.routers.runs.cases.get_settings",
        lambda: Settings(langfuse_host="", langfuse_public_key="", langfuse_secret_key=""),
    )
    response = client.post(f"/api/runs/{rid}/cases/bc_with/agent-chain/sync")

    assert response.status_code == 200
    assert response.json()["trace"]["agent_chain"]["status"] == "unconfigured"
    reloaded = client.get(f"/api/runs/{rid}/cases/bc_with").json()
    assert reloaded["trace"]["agent_chain"]["trace_ids"] == ["cx-trace-1"]
