"""LLMJudge emit 受控 FailureTag 单测（change llm-judge-emit-failure-tags）。

覆盖 judging-pipeline spec「LLMJudge 必须在维度失败时 emit 受控 FailureTag」：
  - 低分维度 emit 对应 tag；过线维度不 emit
  - triage_quality 故意不映射（归 HardGate）
  - 未启用 / 调用失败不产出脏 tag
  - 维度→标签映射纳入 fingerprint
"""

from __future__ import annotations

import asyncio

import medeval.judges.llm as llm_mod
from medeval.judges.llm import LLMJudge
from medeval.models import (
    ChatMessage,
    ConversationTrace,
    FailureTag,
    Level,
    Rubric,
    RubricItem,
    TestCase,
    Turn,
)


def _case() -> TestCase:
    return TestCase(
        sample_id="ft",
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content="hi")],
        rubric=Rubric(
            empathy=RubricItem(max=4),
            differential_thinking=RubricItem(max=4),
            triage_quality=RubricItem(max=4),
            factual_accuracy=RubricItem(max=4),
            multi_turn_consistency=RubricItem(max=4),
            inquiry_completeness=RubricItem(max=4),
        ),
    )


def _trace() -> ConversationTrace:
    return ConversationTrace(messages=[ChatMessage(role="assistant", content="answer")])


def _scripted_judge(scores: dict[str, int]) -> LLMJudge:
    j = LLMJudge(enabled=False)
    j.enabled = True

    async def fake_call(model, prompt):
        return dict(scores), {k: f"r-{v}" for k, v in scores.items()}

    j._call = fake_call  # type: ignore[assignment]
    return j


def _by(scores: dict[str, int]):
    verdicts = asyncio.run(_scripted_judge(scores).judge(_case(), _trace()))
    return {v.name: v for v in verdicts}


def test_low_empathy_emits_empathy_miss():
    by = _by({"empathy": 1})
    assert FailureTag.EMPATHY_MISS in by["llm.empathy"].failure_tags


def test_each_low_dim_emits_mapped_tag():
    by = _by(
        {
            "differential_thinking": 1,
            "factual_accuracy": 0,
            "multi_turn_consistency": 1,
            "inquiry_completeness": 0,
        }
    )
    assert FailureTag.DIFFERENTIAL_NARROW in by["llm.differential_thinking"].failure_tags
    assert FailureTag.MEDICAL_HALLUCINATION in by["llm.factual_accuracy"].failure_tags
    assert FailureTag.DIALOG_BREAK in by["llm.multi_turn_consistency"].failure_tags
    assert FailureTag.INQUIRY_INCOMPLETE in by["llm.inquiry_completeness"].failure_tags


def test_passing_dim_emits_no_tag():
    # max=4 → passed 阈值为 score>=2
    by = _by({"empathy": 2, "factual_accuracy": 4})
    assert by["llm.empathy"].failure_tags == []
    assert by["llm.factual_accuracy"].failure_tags == []


def test_triage_low_does_not_emit_tag():
    by = _by({"triage_quality": 0})
    assert by["llm.triage_quality"].failure_tags == []


def test_disabled_judge_emits_no_tag():
    j = LLMJudge(enabled=False)
    verdicts = asyncio.run(j.judge(_case(), _trace()))
    assert all(v.failure_tags == [] for v in verdicts)


def test_call_failure_emits_no_tag():
    j = LLMJudge(enabled=False)
    j.enabled = True

    async def boom(model, prompt):
        raise RuntimeError("backend down")

    j._call = boom  # type: ignore[assignment]
    verdicts = asyncio.run(j.judge(_case(), _trace()))
    assert all(v.failure_tags == [] for v in verdicts)


def test_dim_tag_mapping_in_fingerprint(monkeypatch):
    fp_before = LLMJudge().fingerprint()
    monkeypatch.setitem(llm_mod._DIM_FAILURE_TAG, "empathy", FailureTag.DIALOG_BREAK)
    fp_after = LLMJudge().fingerprint()
    assert fp_before != fp_after
