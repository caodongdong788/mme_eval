"""性能延迟指标单测。

覆盖 OpenSpec change add-latency-metrics 的核心场景：
  - runner 记录逐轮耗时 + 总耗时，且不影响判分
  - N=3 时 per_run_latency_ms 长度为 3
  - latency_summary 含 avg/median/p90/max，错误 run 被排除
"""

from __future__ import annotations

import asyncio

from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse
from medeval.models import (
    CaseEvaluation,
    CaseResult,
    ChatMessage,
    ConversationTrace,
    Level,
    RunReport,
    TestCase,
    Turn,
)
from medeval.reporter import build_report
from medeval.reporter.markdown_report import render_markdown
from medeval.runner import fold_n_runs, run_cases


class _Adapter(BaseAdapter):
    name = "stub"

    def __init__(self):
        self.n = 0

    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.n += 1
        return ChatResponse(reply=f"reply-{self.n}", raw={"ttft_ms": 12.0})

    async def close(self) -> None:
        pass


def _case(sid: str = "a", turns: int = 1) -> TestCase:
    return TestCase(
        schema_version="2.0",
        sample_id=sid,
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content=f"q{i}") for i in range(turns)],
        evaluation=CaseEvaluation(),
    )


def _result(
    passed: bool,
    duration_ms: int,
    error: str | None = None,
    ttft_ms: float | None = None,
) -> CaseResult:
    trace = ConversationTrace(
        messages=[ChatMessage(role="assistant", content="x")],
        duration_ms=duration_ms,
        turn_ttft_ms=[ttft_ms] if ttft_ms is not None else [],
        error=error,
    )
    return CaseResult(
        case=_case(),
        trace=trace,
        verdicts=[],
        medical_safety_passed=passed,
        release_passed=passed,
    )


# ---------------------------------------------------------------------------
# runner 计时 + 判分零耦合


def test_runner_records_turn_and_total_latency():
    adapter = _Adapter()
    traces = asyncio.run(
        run_cases([_case(turns=3)], adapter, concurrency=1, retry=0)
    )
    trace = traces[0][0]
    assert len(trace.turn_latencies_ms) == 3
    assert all(t >= 0 for t in trace.turn_latencies_ms)
    assert len(trace.turn_ttft_ms) == 3
    assert all(t >= 12 for t in trace.turn_ttft_ms)
    assert trace.duration_ms >= 0


# ---------------------------------------------------------------------------
# N-runs 收集 + 聚合


def test_fold_collects_per_run_latency():
    runs = [_result(True, 100), _result(True, 200), _result(False, 300)]
    folded = fold_n_runs([runs])
    assert folded[0].per_run_latency_ms == [100.0, 200.0, 300.0]


def test_latency_summary_keys_and_values():
    results = [_result(True, 100), _result(True, 300), _result(True, 500)]
    report = build_report("t", results, adapter_type="stub")
    ls = report.latency_summary
    assert set(ls) >= {"count", "avg_ms", "median_ms", "p90_ms", "max_ms"}
    assert ls["count"] == 3
    assert ls["avg_ms"] == 300.0
    assert ls["median_ms"] == 300.0
    assert ls["max_ms"] == 500.0


def test_ttft_summary_uses_streaming_measurements_and_ignores_missing_history():
    results = [
        _result(True, 100, ttft_ms=20),
        _result(True, 200, ttft_ms=40),
        _result(True, 300),
    ]
    report = build_report("t", results, adapter_type="stub")
    assert report.ttft_summary == {
        "count": 2,
        "avg_ms": 30.0,
        "median_ms": 30.0,
        "p90_ms": 40.0,
        "max_ms": 40.0,
    }


def test_error_run_excluded_from_latency():
    ok = _result(True, 100)
    bad = _result(False, 9999, error="adapter exception")
    report = build_report("t", [ok, bad], adapter_type="stub")
    assert report.latency_summary["count"] == 1
    assert report.latency_summary["max_ms"] == 100.0


def test_no_latency_data_renders_na():
    # 用例报错 → 无可用延迟 → 报告显示 N/A 而非空表
    bad = _result(False, 0, error="boom")
    report = build_report("t", [bad], adapter_type="stub")
    assert report.latency_summary == {}
    md = render_markdown(report)
    assert "性能（仅记录）" in md
    assert "无可用延迟数据" in md
