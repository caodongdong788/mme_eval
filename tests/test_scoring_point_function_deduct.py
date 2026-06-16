"""指南得分点只减不加：总扣分 ×0.1 映射功能分（change scoring-point-deduct-only）。"""

from __future__ import annotations

import pytest

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
from medeval.reporter.scoring import (
    SCORING_POINT_FUNCTION_PER_POINT,
    score_case,
    scoring_point_miss_pts,
)


def _case(**kwargs) -> TestCase:
    base = dict(
        sample_id="spd",
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


def _by_name(verdicts: list[JudgeVerdict]) -> dict[str, JudgeVerdict]:
    return {v.name: v for v in verdicts}


def test_per_point_constant():
    assert SCORING_POINT_FUNCTION_PER_POINT == 0.1


def test_miss_pts_positive_and_negative():
    case = _case(
        scoring_points=[
            ScoringPoint(criterion="应说A", points=3),
            ScoringPoint(criterion="禁说B", points=-3),
        ]
    )
    verdicts = [
        JudgeVerdict(name="scoring_point.point0", passed=False, score=0, max_score=3),
        JudgeVerdict(name="scoring_point.point1", passed=False, score=-3, max_score=0),
    ]
    miss, cure = scoring_point_miss_pts(case, _by_name(verdicts))
    assert miss == 6.0
    assert cure is False


def test_hit_all_positive_no_function_deduct():
    case = _case(scoring_points=[ScoringPoint(criterion="a", points=3)])
    verdicts = [
        JudgeVerdict(name="rule.must_have", passed=True),
        JudgeVerdict(name="scoring_point.point0", passed=True, score=3, max_score=3),
    ]
    bd = score_case(_result(case, verdicts))
    assert bd["dimensions"]["function"] == pytest.approx(0.37)
    assert not any("指南得分点" in d for d in bd["deductions"])


def test_miss_three_pts_deducts_03():
    case = _case(scoring_points=[ScoringPoint(criterion="a", points=3)])
    verdicts = [
        JudgeVerdict(name="rule.must_have", passed=True),
        JudgeVerdict(name="scoring_point.point0", passed=False, score=0, max_score=3),
    ]
    bd = score_case(_result(case, verdicts))
    assert bd["dimensions"]["function"] == pytest.approx(0.37 - 0.3)


def test_partial_hit_no_boost_only_deduct():
    case = _case(
        scoring_points=[
            ScoringPoint(criterion="a", points=3),
            ScoringPoint(criterion="b", points=3),
        ]
    )
    verdicts = [
        JudgeVerdict(
            name="rule.must_have",
            passed=False,
            unmet_patterns=[{"keyword": "就医"}],
        ),
        JudgeVerdict(name="scoring_point.point0", passed=True, score=3, max_score=3),
        JudgeVerdict(name="scoring_point.point1", passed=False, score=0, max_score=3),
    ]
    bd = score_case(_result(case, verdicts))
    # 0.37 - 0.15 (must_have) - 0.3 (miss 3 pts), 无加分
    assert bd["dimensions"]["function"] == pytest.approx(0.37 - 0.15 - 0.3)


def test_negative_hit_single_line_no_double_deduct():
    case = _case(scoring_points=[ScoringPoint(criterion="bad", points=-3)])
    verdicts = [
        JudgeVerdict(name="rule.must_have", passed=True),
        JudgeVerdict(name="scoring_point.point0", passed=False, score=-3, max_score=0),
    ]
    bd = score_case(_result(case, verdicts))
    assert bd["dimensions"]["function"] == pytest.approx(0.37 - 0.3)
    sp_deductions = [d for d in bd["deductions"] if "指南得分点" in d]
    assert len(sp_deductions) == 1


def test_function_can_go_negative():
    case = _case(
        scoring_points=[
            ScoringPoint(criterion="a", points=3),
            ScoringPoint(criterion="b", points=3),
        ]
    )
    verdicts = [
        JudgeVerdict(
            name="rule.must_have",
            passed=False,
            unmet_patterns=[{"keyword": "a"}, {"keyword": "b"}],
        ),
        JudgeVerdict(name="scoring_point.point0", passed=False, score=0, max_score=3),
        JudgeVerdict(name="scoring_point.point1", passed=False, score=0, max_score=3),
    ]
    bd = score_case(_result(case, verdicts))
    assert bd["dimensions"]["function"] < 0
