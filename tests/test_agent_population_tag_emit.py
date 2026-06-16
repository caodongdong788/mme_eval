"""agent 用例 + population_blind emit（change agent-population-tag-emit）。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from medeval.judges.rule import RuleJudge
from medeval.loader import load_cases
from medeval.models import (
    ChatMessage,
    ConversationTrace,
    ExpectedBehavior,
    FailureTag,
    Level,
    Pattern,
    ScoreProfile,
    TestCase,
    Turn,
)

_ROOT = Path(__file__).resolve().parents[1]
_BC = _ROOT / "cases" / "breast_cancer"


def _trace(reply: str = "请多喝水休息") -> ConversationTrace:
    return ConversationTrace(
        messages=[ChatMessage(role="assistant", content=reply)]
    )


def _population_case() -> TestCase:
    return TestCase(
        sample_id="pop",
        scenario="特殊人群",
        level=Level.L2,
        score_profile=ScoreProfile.population,
        turns=[Turn(content="孕期化疗")],
        expected_behavior=ExpectedBehavior(
            must_have_all=True,
            must_have=[
                Pattern(regex=r"产科", note="产科评估"),
            ],
        ),
    )


def test_population_must_have_fail_emits_population_blind():
    verdicts = asyncio.run(
        RuleJudge().judge(_population_case(), _trace("一般问题不大"))
    )
    mh = next(v for v in verdicts if v.name == "rule.must_have")
    assert not mh.passed
    assert FailureTag.POPULATION_BLIND in mh.failure_tags
    assert FailureTag.INQUIRY_INCOMPLETE not in mh.failure_tags


def test_non_population_must_have_still_emits_inquiry_incomplete():
    case = _population_case()
    case.score_profile = ScoreProfile.knowledge
    verdicts = asyncio.run(RuleJudge().judge(case, _trace("一般问题不大")))
    mh = next(v for v in verdicts if v.name == "rule.must_have")
    assert FailureTag.INQUIRY_INCOMPLETE in mh.failure_tags


def test_agent_yaml_at_least_eight_cases():
    cases = yaml.safe_load((_BC / "agent.yaml").read_text(encoding="utf-8"))
    assert len(cases) >= 8
    assert all(c.get("score_profile") == "agent" for c in cases)


def test_agent_cases_load_in_suite():
    cases = load_cases(include=["cases/breast_cancer"], base_dir=_ROOT)
    agent = [c for c in cases if c.score_profile == ScoreProfile.agent]
    assert len(agent) >= 8
