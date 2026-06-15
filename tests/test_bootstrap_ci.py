"""bootstrap 置信区间单测（enhance-eval-engine Phase 1）。

覆盖：
  - 已知分布的点估计与区间边界合理性
  - 空样本返回空 dict、不抛错
  - 全过/全挂时区间退化到边界
  - 给定 seed 结果可复现
  - build_report 基于 release_passed 产出 pass_rate_ci；关闭统计时为空
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
from medeval.reporter.markdown_report import render_markdown
from medeval.reporter.stats import bootstrap_ci


def _case(sid: str = "a") -> TestCase:
    return TestCase(
        sample_id=sid,
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content="q")],
    )


def _result(release_passed: bool, sid: str = "a") -> CaseResult:
    trace = ConversationTrace(
        messages=[ChatMessage(role="assistant", content="本回答仅供参考")],
        duration_ms=100,
    )
    cr = CaseResult(
        case=_case(sid),
        trace=trace,
        verdicts=[],
        hard_gate_passed=release_passed,
        gate_passed=release_passed,
    )
    # build_report 内部 apply_grading 会重算 release_passed；此处仅备结构。
    return cr


# ---------------------------------------------------------------------------
# 纯函数 bootstrap_ci


def test_bootstrap_empty_returns_empty():
    assert bootstrap_ci([]) == {}


def test_bootstrap_all_pass_interval_at_one():
    ci = bootstrap_ci([True] * 20, n_resamples=500, confidence=0.95, seed=0)
    assert ci["point"] == 1.0
    assert ci["low"] == 1.0
    assert ci["high"] == 1.0
    assert ci["n"] == 20


def test_bootstrap_all_fail_interval_at_zero():
    ci = bootstrap_ci([False] * 20, n_resamples=500, confidence=0.95, seed=0)
    assert ci["point"] == 0.0
    assert ci["low"] == 0.0
    assert ci["high"] == 0.0


def test_bootstrap_point_and_bounds_order():
    samples = [True] * 7 + [False] * 3  # point = 0.7
    ci = bootstrap_ci(samples, n_resamples=1000, confidence=0.95, seed=0)
    assert abs(ci["point"] - 0.7) < 1e-9
    assert 0.0 <= ci["low"] <= ci["point"] <= ci["high"] <= 1.0
    assert ci["confidence"] == 0.95


def test_bootstrap_seed_reproducible():
    s = [True, False, True, True, False, True, False, False, True, True]
    a = bootstrap_ci(s, n_resamples=800, confidence=0.9, seed=42)
    b = bootstrap_ci(s, n_resamples=800, confidence=0.9, seed=42)
    assert a == b
    c = bootstrap_ci(s, n_resamples=800, confidence=0.9, seed=7)
    # 不同 seed 区间边界一般不同（点估计相同）
    assert c["point"] == a["point"]


def test_bootstrap_zero_resamples_degenerate():
    ci = bootstrap_ci([True, False], n_resamples=0, seed=0)
    assert ci["point"] == 0.5
    assert ci["low"] == ci["high"] == 0.5


# ---------------------------------------------------------------------------
# build_report 集成


def test_build_report_fills_pass_rate_ci_by_default():
    results = [_result(True, f"p{i}") for i in range(8)] + [
        _result(False, f"f{i}") for i in range(2)
    ]
    report = build_report("t", results, adapter_type="stub")
    ci = report.pass_rate_ci
    assert ci, "默认应产出置信区间"
    assert "low" in ci and "high" in ci and "point" in ci
    assert ci["n"] == 10
    assert ci["low"] <= ci["point"] <= ci["high"]


def test_build_report_stats_disabled_via_config_snapshot():
    results = [_result(True, f"p{i}") for i in range(5)]
    snapshot = {"run": {"stats": {"enabled": False}}}
    report = build_report(
        "t", results, adapter_type="stub", config_snapshot=snapshot
    )
    assert report.pass_rate_ci == {}


def test_build_report_empty_results_no_ci():
    report = build_report("t", [], adapter_type="stub")
    assert report.pass_rate_ci == {}


def test_markdown_renders_ci_suffix():
    results = [_result(True, f"p{i}") for i in range(6)] + [_result(False, "f0")]
    report = build_report("t", results, adapter_type="stub")
    md = render_markdown(report)
    assert "置信区间" in md
