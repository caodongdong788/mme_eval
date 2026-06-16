"""用例明细暴露 Langfuse 深链：cases 列表带 langfuse_trace_url；缺失安全回退 None。"""

from __future__ import annotations

from factories import make_case_result, make_report

from medeval.models import ChatMessage, ConversationTrace
from server.benchmarks import ensure_builtin_benchmark
from server.db import session_scope
from server.ingest import ingest_report


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
        bm = ensure_builtin_benchmark(s, settings)
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
