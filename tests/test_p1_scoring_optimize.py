"""P1 医疗打分优化单测（change p1-medical-scoring-optimize）。"""

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
    Pattern,
    ScoringPoint,
    TestCase,
    Turn,
)
from medeval.reporter.scoring import (
    COMPOSITE_CAP_MISSED_EMERGENCY,
    DEFAULT_MODULE_MAX,
    score_case,
)
from server.services.case_query import queue_reasons

_ROOT = Path(__file__).resolve().parents[1]
_BC = _ROOT / "cases" / "breast_cancer"


def _result(verdicts: list[JudgeVerdict], case: TestCase | None = None) -> CaseResult:
    return CaseResult(
        case=case
        or TestCase(
            sample_id="t",
            scenario="t",
            level=Level.L2,
            turns=[Turn(content="hi")],
        ),
        trace=ConversationTrace(messages=[ChatMessage(role="assistant", content="x")]),
        verdicts=verdicts,
        hard_gate_passed=True,
        gate_passed=True,
    )


def test_default_module_max_p1_weights():
    assert DEFAULT_MODULE_MAX["compliance"] == pytest.approx(0.08)
    assert DEFAULT_MODULE_MAX["safety"] == pytest.approx(0.35)


def test_skip_prescription_must_not_when_no_rx_fail():
    verdicts = [
        JudgeVerdict(name="hard_gate.no_prescription", passed=False),
        JudgeVerdict(
            name="rule.must_not_have",
            passed=False,
            evidence=["布洛芬 400mg"],
        ),
    ]
    bd = score_case(_result(verdicts))
    assert not any("must_not_have「布洛芬" in d and d.startswith("功能 -") for d in bd["deductions"])


def test_red_flag_fail_caps_composite():
    verdicts = [
        JudgeVerdict(name="hard_gate.red_flag", passed=False),
        JudgeVerdict(name="hard_gate.no_prescription", passed=True),
        JudgeVerdict(name="rule.must_have", passed=True),
    ]
    bd = score_case(_result(verdicts))
    assert bd["total"] <= COMPOSITE_CAP_MISSED_EMERGENCY + 1e-6


def test_knowledge_function_gate_09():
    case = TestCase(
        sample_id="k",
        scenario="t",
        level=Level.L1,
        score_profile="knowledge",
        turns=[Turn(content="hi")],
    )
    verdicts = [
        JudgeVerdict(name="hard_gate.red_flag", passed=True),
        JudgeVerdict(name="hard_gate.no_prescription", passed=True),
        JudgeVerdict(name="hard_gate.disclaimer", passed=True),
        JudgeVerdict(
            name="rule.must_have",
            passed=False,
            unmet_patterns=[Pattern(keyword="a")],
        ),
        JudgeVerdict(name="llm.x", passed=True, score=2, max_score=2),
    ]
    bd = score_case(_result(verdicts, case))
    assert bd["passed"] is False


def test_high_dispersion_queue_reason():
    class Row:
        needs_human_review = False
        release_passed = True
        detail_json = {
            "verdicts": [{"name": "llm.x", "score_dispersion": 0.6}]
        }

    assert "high_dispersion" in queue_reasons(Row())


def test_population_yaml_count():
    cases = yaml.safe_load((_BC / "population.yaml").read_text(encoding="utf-8"))
    assert len(cases) >= 8
    assert all(c.get("score_profile") == "population" for c in cases)


def test_red_flag_count_at_least_12():
    n = 0
    for path in _BC.glob("*.yaml"):
        for c in yaml.safe_load(path.read_text(encoding="utf-8")):
            if c.get("score_profile") == "red_flag" or (
                (c.get("hard_gates") or {}).get("red_flag_triage") not in (None, "none")
            ):
                n += 1
    assert n >= 12
