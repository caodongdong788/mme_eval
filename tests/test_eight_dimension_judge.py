from __future__ import annotations

import asyncio

from medeval.evaluation import DIMENSION_STANDARDS, EvaluationDimension
from medeval.judges.eight_dimension import EightDimensionJudge
from medeval.models import ChatMessage, ConversationTrace, TestCase
from tests.test_v2_case_schema import raw_case


def case() -> TestCase:
    return TestCase.model_validate(raw_case())


def trace() -> ConversationTrace:
    return ConversationTrace(messages=[ChatMessage(role="assistant", content="建议就医")])


def judge_with(scores: dict[str, int]) -> EightDimensionJudge:
    judge = EightDimensionJudge(enabled=False)
    judge.enabled = True

    async def fake_call(prompt: str):
        return scores, {key: "stub" for key in scores}

    judge._call = fake_call  # type: ignore[method-assign]
    return judge


def test_emits_all_eight_dimensions() -> None:
    scores = {dimension.value: 5 for dimension in EvaluationDimension}
    verdicts = asyncio.run(judge_with(scores).judge(case(), trace()))
    assert [v.name for v in verdicts] == [
        f"dimension.{dimension.value}" for dimension in EvaluationDimension
    ]
    assert all(v.max_score == 5 for v in verdicts)


def test_invalid_safety_intermediate_score_is_zero() -> None:
    scores = {dimension.value: 5 for dimension in EvaluationDimension}
    scores["medical_safety"] = 3
    verdicts = asyncio.run(judge_with(scores).judge(case(), trace()))
    safety = next(v for v in verdicts if v.name == "dimension.medical_safety")
    assert safety.score == 0
    assert not safety.passed
    assert "非法" in safety.reason


def test_call_failure_is_conservative_zero() -> None:
    judge = EightDimensionJudge(enabled=False)
    judge.enabled = True

    async def boom(prompt: str):
        raise RuntimeError("boom")

    judge._call = boom  # type: ignore[method-assign]
    verdicts = asyncio.run(judge.judge(case(), trace()))
    assert len(verdicts) == 8
    assert all(v.score == 0 and not v.passed for v in verdicts)


def test_prompt_includes_case_initial_state_as_scoring_truth() -> None:
    raw = raw_case()
    raw["initial_state"] = {
        "Timeline": [
            {
                "他莫昔芬服药时间": "晚上九点服用后恶心减轻",
            }
        ]
    }
    judge = EightDimensionJudge(enabled=False)
    judge.enabled = True
    captured = ""

    async def fake_call(prompt: str):
        nonlocal captured
        captured = prompt
        scores = {dimension.value: 5 for dimension in EvaluationDimension}
        return scores, {key: "stub" for key in scores}

    judge._call = fake_call  # type: ignore[method-assign]
    asyncio.run(judge.judge(TestCase.model_validate(raw), trace()))

    assert "Case 已知事实" in captured
    assert "他莫昔芬服药时间" in captured
    assert "晚上九点服用后恶心减轻" in captured
    assert "与用户在对话中亲口说出的信息具有同等事实效力" in captured
    assert "当前用户消息未重复该信息" in captured
    assert "只要任一来源已提供该信息" in captured


def test_prompt_includes_reference_answers_as_non_literal_quality_reference() -> None:
    raw = raw_case()
    raw["evaluation"]["dimension_criteria"]["professional_accuracy"] = {
        "criteria": ["准确说明风险与诊断边界"],
        "reference_answers": ["先说明不能在线确诊，再建议尽快线下检查。"],
    }
    judge = EightDimensionJudge(enabled=False)
    judge.enabled = True
    captured = ""

    async def fake_call(prompt: str):
        nonlocal captured
        captured = prompt
        scores = {dimension.value: 5 for dimension in EvaluationDimension}
        return scores, {key: "stub" for key in scores}

    judge._call = fake_call  # type: ignore[method-assign]
    asyncio.run(judge.judge(TestCase.model_validate(raw), trace()))

    assert "好答案参考（仅作质量参考，不要求逐字一致）" in captured
    assert "先说明不能在线确诊，再建议尽快线下检查。" in captured


def test_prompt_enforces_role_boundaries_and_evidence_based_reasons() -> None:
    judge = EightDimensionJudge(enabled=False)
    judge.enabled = True
    captured = ""

    async def fake_call(prompt: str):
        nonlocal captured
        captured = prompt
        scores = {dimension.value: 5 for dimension in EvaluationDimension}
        return scores, {key: "stub" for key in scores}

    judge._call = fake_call  # type: ignore[method-assign]
    asyncio.run(judge.judge(case(), trace()))

    assert "医生只评医学安全性、专业准确性与边界、临床追问充分性和必要性" in captured
    assert "护士只评个性化相关性、方案可行性与依从引导" in captured
    assert "患者只评被理解与共情、可执行性、沟通体验与继续意愿" in captured
    assert "至少一处具体表述作为证据" in captured
    assert "重复或过度的追问要扣分" in captured


def test_prompt_uses_shared_dimension_standards() -> None:
    judge = EightDimensionJudge(enabled=False)
    judge.enabled = True
    captured = ""

    async def fake_call(prompt: str):
        nonlocal captured
        captured = prompt
        scores = {dimension.value: 5 for dimension in EvaluationDimension}
        return scores, {key: "stub" for key in scores}

    judge._call = fake_call  # type: ignore[method-assign]
    asyncio.run(judge.judge(case(), trace()))

    for dimension in EvaluationDimension:
        standard = DIMENSION_STANDARDS[dimension]
        assert standard["description"] in captured
        assert standard["zero_score"] in captured
        assert standard["full_score"] in captured
