"""Test N-runs majority voting aggregator (change harden-evaluation-determinism)."""

from __future__ import annotations

from datetime import datetime

from medeval.models import (
    CaseResult,
    ConversationTrace,
    HardGates,
    Level,
    TestCase,
    Turn,
)
from medeval.runner import fold_n_runs


def _make_case(sample_id: str = "tc") -> TestCase:
    return TestCase(
        sample_id=sample_id,
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content="x")],
    )


def _make_result(case: TestCase, passed: bool) -> CaseResult:
    return CaseResult(
        case=case,
        trace=ConversationTrace(messages=[]),
        verdicts=[],
        hard_gate_passed=passed,
        gate_passed=passed,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )


def test_fold_n1_passthrough():
    case = _make_case()
    folded = fold_n_runs([[_make_result(case, True)]])
    assert len(folded) == 1
    r = folded[0]
    assert r.gate_passed is True
    assert r.n_runs == 1
    assert r.per_run_gate_passed == [True]
    assert r.stability == "stable_pass"


def test_fold_n1_fail():
    case = _make_case()
    folded = fold_n_runs([[_make_result(case, False)]])
    r = folded[0]
    assert r.stability == "stable_fail"
    assert r.per_run_gate_passed == [False]


def test_fold_n3_majority_pass():
    case = _make_case()
    runs = [
        _make_result(case, True),
        _make_result(case, True),
        _make_result(case, False),
    ]
    folded = fold_n_runs([runs])
    r = folded[0]
    assert r.gate_passed is True
    assert r.n_runs == 3
    assert r.per_run_gate_passed == [True, True, False]
    assert r.stability == "flaky"


def test_fold_n3_majority_fail():
    case = _make_case()
    runs = [
        _make_result(case, True),
        _make_result(case, False),
        _make_result(case, False),
    ]
    folded = fold_n_runs([runs])
    r = folded[0]
    assert r.gate_passed is False
    assert r.stability == "flaky"


def test_fold_n3_stable_pass():
    case = _make_case()
    runs = [_make_result(case, True) for _ in range(3)]
    folded = fold_n_runs([runs])
    assert folded[0].stability == "stable_pass"
    assert folded[0].gate_passed is True


def test_fold_n3_stable_fail():
    case = _make_case()
    runs = [_make_result(case, False) for _ in range(3)]
    folded = fold_n_runs([runs])
    assert folded[0].stability == "stable_fail"
    assert folded[0].gate_passed is False


def test_fold_n4_tie_counts_as_fail():
    """N=4 时 2 过 2 挂必须算挂（严格过半未达）。"""
    case = _make_case()
    runs = [
        _make_result(case, True),
        _make_result(case, True),
        _make_result(case, False),
        _make_result(case, False),
    ]
    folded = fold_n_runs([runs])
    r = folded[0]
    assert r.gate_passed is False
    assert r.stability == "flaky"


def test_fold_n5_majority_pass_3of5():
    case = _make_case()
    runs = [
        _make_result(case, True),
        _make_result(case, True),
        _make_result(case, True),
        _make_result(case, False),
        _make_result(case, False),
    ]
    folded = fold_n_runs([runs])
    assert folded[0].gate_passed is True
    assert folded[0].stability == "flaky"


def test_representative_trace_is_earliest_match():
    """代表 trace 选取：与 majority 一致的最早一次。"""
    case = _make_case()
    # mark 不同的 trace 内容以区分代表 trace
    r0 = _make_result(case, False)
    r0.trace = ConversationTrace(messages=[], duration_ms=10)
    r1 = _make_result(case, True)
    r1.trace = ConversationTrace(messages=[], duration_ms=20)
    r2 = _make_result(case, True)
    r2.trace = ConversationTrace(messages=[], duration_ms=30)
    folded = fold_n_runs([[r0, r1, r2]])
    rep = folded[0]
    assert rep.gate_passed is True  # majority pass
    # 代表 trace 应是 r1（最早的 pass run），duration=20
    assert rep.trace.duration_ms == 20


def test_multiple_cases_independent_folding():
    case_a = _make_case("a")
    case_b = _make_case("b")
    folded = fold_n_runs(
        [
            [_make_result(case_a, True), _make_result(case_a, True)],
            [_make_result(case_b, False), _make_result(case_b, False)],
        ]
    )
    assert len(folded) == 2
    assert folded[0].case.sample_id == "a"
    assert folded[0].gate_passed is True
    assert folded[0].stability == "stable_pass"
    assert folded[1].case.sample_id == "b"
    assert folded[1].gate_passed is False
    assert folded[1].stability == "stable_fail"
