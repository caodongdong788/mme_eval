"""Test backwards compatibility for models with N-runs fields.

Old report.json files (pre-`harden-evaluation-determinism`) lack `stability` /
`n_runs` / `per_run_passed` / `stability_distribution` fields.  Loading them
must succeed and fall back to sensible defaults.
"""

from __future__ import annotations

from medeval.models import CaseResult, ConversationTrace, Level, RunReport, TestCase, Turn


def test_caseresult_defaults_for_legacy_payload():
    legacy = {
        "case": {
            "sample_id": "x",
            "scenario": "s",
            "level": "L2",
            "turns": [{"role": "user", "content": "hi"}],
        },
        "trace": {"messages": []},
        "verdicts": [],
        "hard_gate_passed": True,
        "gate_passed": True,
    }
    r = CaseResult.model_validate(legacy)
    assert r.n_runs == 1
    assert r.per_run_gate_passed == []
    assert r.stability == "stable_pass"


def test_runreport_defaults_for_legacy_payload():
    legacy = {
        "run_name": "old",
        "results": [],
    }
    rep = RunReport.model_validate(legacy)
    assert rep.n_runs == 1
    assert rep.stability_distribution == {}


def test_caseresult_serialization_roundtrip():
    """新 schema 序列化 + 反序列化必须保留 N-runs 字段。"""
    case = TestCase(
        sample_id="t",
        scenario="s",
        level=Level.L2,
        turns=[Turn(role="user", content="hi")],
    )
    r = CaseResult(
        case=case,
        trace=ConversationTrace(messages=[]),
        verdicts=[],
        hard_gate_passed=True,
        gate_passed=True,
        n_runs=3,
        per_run_gate_passed=[True, True, False],
        stability="flaky",
    )
    js = r.model_dump_json()
    r2 = CaseResult.model_validate_json(js)
    assert r2.n_runs == 3
    assert r2.per_run_gate_passed == [True, True, False]
    assert r2.stability == "flaky"
