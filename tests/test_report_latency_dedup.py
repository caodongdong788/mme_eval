"""去重：有版本对比性能块时不再渲染独立「性能（仅记录）」段；表头改名「变化」。

参见 OpenSpec change dedup-latency-report。
"""

from __future__ import annotations

from medeval.models import (
    CaseResult,
    ChatMessage,
    ConversationTrace,
    Level,
    TestCase,
    Turn,
)
from medeval.reporter import build_report
from medeval.reporter.diff import _latency_diff
from medeval.reporter.markdown_report import render_markdown


def _result(duration_ms: int) -> CaseResult:
    return CaseResult(
        case=TestCase(
            sample_id="a",
            scenario="t",
            level=Level.L2,
            turns=[Turn(role="user", content="q")],
        ),
        trace=ConversationTrace(
            messages=[ChatMessage(role="assistant", content="x")],
            duration_ms=duration_ms,
        ),
        verdicts=[],
        hard_gate_passed=True,
        gate_passed=True,
    )


def _report_with_latency():
    return build_report("t", [_result(100), _result(300)], adapter_type="stub")


# diff_summary 里含「性能变化」块的桩
_DIFF_WITH_PERF = (
    "**总通过率：** 100.0% (上版 90.0%，+10.0pp)\n\n"
    "**性能变化（会话延迟，仅记录不计分）：** 单位 ms，↑ 变慢 / ↓ 变快\n\n"
    "| 指标 | 当前 | 上版 | 变化 |\n|-|-|-|-|\n| 平均 | 200 | 300 | -100 (↓ -33.3%) |"
)


def test_standalone_perf_hidden_when_diff_has_perf_block():
    md = render_markdown(_report_with_latency(), diff_summary=_DIFF_WITH_PERF)
    assert "## 性能（仅记录）" not in md


def test_standalone_perf_shown_when_no_diff():
    md = render_markdown(_report_with_latency(), diff_summary="")
    assert "## 性能（仅记录）" in md


def test_standalone_perf_shown_when_diff_lacks_perf_block():
    # diff 存在但上版无延迟 → 没有「性能变化」块 → 独立段兜底
    diff = "**总通过率：** 100.0%\n> ℹ️ 上版本未记录延迟数据，无法对比性能。"
    md = render_markdown(_report_with_latency(), diff_summary=diff)
    assert "## 性能（仅记录）" in md


def test_latency_diff_column_named_bianhua():
    cur = {"latency_summary": {"count": 1, "avg_ms": 200.0, "median_ms": 200.0, "p90_ms": 200.0, "max_ms": 200.0}}
    prev = {"latency_summary": {"count": 1, "avg_ms": 300.0, "median_ms": 300.0, "p90_ms": 300.0, "max_ms": 300.0}}
    out = _latency_diff(cur, prev)
    assert "| 指标 | 当前 | 上版 | 变化 |" in out
    assert "| 指标 | 当前 | 上版 | Δ |" not in out
