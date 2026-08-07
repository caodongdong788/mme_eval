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


def test_case_detail_rewrites_legacy_cx_share_origin_without_mutating_result(
    client, settings
):
    rid = _seed(settings)
    legacy_url = "http://10.30.7.71/s/evaluation-token?source=mme#turn-1"
    with session_scope() as session:
        row = session.query(CaseResultRow).filter_by(run_id=rid, sample_id="bc_with").one()
        detail = dict(row.detail_json)
        detail["trace"] = {
            **detail["trace"],
            "cx_evaluation_share_url": legacy_url,
        }
        row.detail_json = detail

    response = client.get(f"/api/runs/{rid}/cases/bc_with")

    assert response.status_code == 200
    assert response.json()["trace"]["cx_evaluation_share_url"] == (
        "https://sit-cx.senzco.com/s/evaluation-token?source=mme#turn-1"
    )
    with session_scope() as session:
        stored = session.query(CaseResultRow).filter_by(run_id=rid, sample_id="bc_with").one()
        assert stored.detail_json["trace"]["cx_evaluation_share_url"] == legacy_url


def test_case_detail_defers_raw_agent_chain_and_rag_audit(client, settings):
    rid = _seed(settings)
    audit = {
        "id": "rag-1",
        "status": "available",
        "counts": {"searched": 25, "qualified": 20, "candidates": 5, "selected": 2},
        "selected_sources": [{"id": "doc-1", "title": "指南", "chunks": [{"content": "x" * 2000}]}],
    }
    with session_scope() as session:
        row = session.query(CaseResultRow).filter_by(run_id=rid, sample_id="bc_with").one()
        detail = dict(row.detail_json)
        detail["trace"] = {
            **detail["trace"],
            "cx_literature_audits": [audit],
            "agent_chain": {
                "status": "synced",
                "trace_ids": ["trace-1"],
                "nodes": [{"id": "raw", "input": "x" * 100_000, "output": "y" * 100_000}],
                "summary": {
                    "steps": [],
                    "sources": [{"key": "literature_rag", "calls": 1, "rag_audit": [audit]}],
                    "risks": [],
                    "actions": [],
                    "quality": {},
                },
            },
        }
        row.detail_json = detail

    compact = client.get(f"/api/runs/{rid}/cases/bc_with")
    assert compact.status_code == 200
    chain = compact.json()["trace"]["agent_chain"]
    assert "nodes" not in chain
    assert "rag_audit" not in chain["summary"]["sources"][0]
    assert "cx_literature_audits" not in compact.json()["trace"]

    full = client.get(f"/api/runs/{rid}/cases/bc_with/agent-chain/rag-audit")
    assert full.status_code == 200
    assert full.json()["calls"][0]["id"] == "rag-1"


def test_next_case_endpoint_reads_only_next_sample(client, settings):
    rid = _seed(settings)
    assert client.get(f"/api/runs/{rid}/cases/bc_with/next").json() == {"sample_id": "bc_without"}
    assert client.get(f"/api/runs/{rid}/cases/bc_without/next").json() == {"sample_id": None}


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
