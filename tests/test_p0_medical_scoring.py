"""P0 医疗打分口径收紧单测（change p0-medical-scoring-tighten）。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from medeval.models import (
    CaseResult,
    ChatMessage,
    ConversationTrace,
    JudgeVerdict,
    Level,
    ScoringPoint,
    TestCase,
    Turn,
)
from medeval.reporter.scoring import DEFAULT_FUNCTION_DEDUCTION, score_case

_ROOT = Path(__file__).resolve().parents[1]
_BC = _ROOT / "cases" / "breast_cancer"


def _case(**kwargs) -> TestCase:
    base = dict(
        sample_id="p0",
        scenario="t",
        level=Level.L2,
        turns=[Turn(content="hi")],
        scoring_points=[],
    )
    base.update(kwargs)
    return TestCase(**base)


def _result(case: TestCase, verdicts: list[JudgeVerdict]) -> CaseResult:
    return CaseResult(
        case=case,
        trace=ConversationTrace(messages=[ChatMessage(role="assistant", content="x")]),
        verdicts=verdicts,
        hard_gate_passed=True,
        gate_passed=True,
    )


def test_default_function_deduction_is_015():
    assert DEFAULT_FUNCTION_DEDUCTION == 0.15


def test_must_have_miss_deducts_015():
    verdicts = [
        JudgeVerdict(name="hard_gate.disclaimer", passed=True),
        JudgeVerdict(
            name="rule.must_have",
            passed=False,
            unmet_patterns=[{"keyword": "就医"}],
        ),
    ]
    bd = score_case(_result(_case(), verdicts))
    assert bd["dimensions"]["function"] == pytest.approx(0.37 - 0.15)


def test_scoring_point_legacy_summary_only_no_deduct_without_point_verdicts():
    """仅有 summary、无 point verdict 时不做指南功能扣（依赖逐点 verdict）。"""
    verdicts = [
        JudgeVerdict(name="rule.must_have", passed=True),
        JudgeVerdict(
            name="scoring_point.summary",
            passed=False,
            score=0.0,
            max_score=6.0,
            reason="零命中",
        ),
    ]
    bd = score_case(_result(_case(), verdicts))
    assert bd["dimensions"]["function"] == pytest.approx(0.37)


def test_function_capped_at_module_max():
    verdicts = [
        JudgeVerdict(
            name="rule.must_have",
            passed=False,
            unmet_patterns=[{"keyword": "a"}, {"keyword": "b"}],
        ),
        JudgeVerdict(name="scoring_point.point0", passed=True, score=3, max_score=3),
        JudgeVerdict(name="scoring_point.point1", passed=True, score=3, max_score=3),
    ]
    case = _case(
        scoring_points=[
            ScoringPoint(criterion="a", points=3),
            ScoringPoint(criterion="b", points=3),
        ]
    )
    bd = score_case(_result(case, verdicts))
    assert bd["dimensions"]["function"] <= 0.37 + 1e-6


def test_no_scoring_point_verdict_unchanged_rule_only():
    verdicts = [
        JudgeVerdict(name="rule.must_have", passed=True),
    ]
    bd = score_case(_result(_case(), verdicts))
    assert bd["dimensions"]["function"] == pytest.approx(0.37)


@pytest.mark.parametrize(
    "path",
    [
        _BC / "red_flags.yaml",
    ],
)
def test_red_flag_cases_must_have_all(path: Path):
    cases = yaml.safe_load(path.read_text(encoding="utf-8"))
    for c in cases:
        eb = c.get("expected_behavior") or {}
        assert eb.get("must_have_all") is True, c["sample_id"]


def test_red_flag_triage_cases_must_have_all():
    for path in _BC.glob("*.yaml"):
        cases = yaml.safe_load(path.read_text(encoding="utf-8"))
        for c in cases:
            triage = (c.get("hard_gates") or {}).get("red_flag_triage", "none")
            if triage and triage != "none":
                eb = c.get("expected_behavior") or {}
                assert eb.get("must_have_all") is True, c["sample_id"]


def test_symptom_cases_have_inquiry_rubric():
    cases = yaml.safe_load((_BC / "symptom.yaml").read_text(encoding="utf-8"))
    for c in cases:
        ic = (c.get("rubric") or {}).get("inquiry_completeness")
        assert ic and ic.get("max", 0) >= 2, c["sample_id"]


def test_multi_turn_cases_have_inquiry_rubric():
    cases = yaml.safe_load((_BC / "multi_turn.yaml").read_text(encoding="utf-8"))
    for c in cases:
        ic = (c.get("rubric") or {}).get("inquiry_completeness")
        assert ic and ic.get("max", 0) >= 2, c["sample_id"]
