"""LLMJudge 自定义 prompt_template。"""

from __future__ import annotations

import asyncio

from medeval.judges.llm import LLMJudge
from medeval.models import (
    ChatMessage,
    ConversationTrace,
    Level,
    Rubric,
    RubricItem,
    TestCase,
    Turn,
)


def _case() -> TestCase:
    return TestCase(
        sample_id="pt",
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content="hi")],
        rubric=Rubric(empathy=RubricItem(max=4)),
    )


def _trace() -> ConversationTrace:
    return ConversationTrace(messages=[ChatMessage(role="assistant", content="ok")])


def test_custom_prompt_template_used_in_judge_call():
    custom = "CUSTOM {conversation} | {rubric_text} | {tool_context}"
    j = LLMJudge(enabled=False, prompt_template=custom)
    j.enabled = True
    seen: list[str] = []

    async def fake_call(model, prompt):
        seen.append(prompt)
        return {"empathy": 3}, {"empathy": "ok"}, []

    j._call = fake_call  # type: ignore[assignment]
    asyncio.run(j.judge(_case(), _trace()))
    assert len(seen) == 1
    assert seen[0].startswith("CUSTOM ")
    assert "[turn" in seen[0] or "bot" in seen[0].lower() or "user" in seen[0].lower()


def test_empty_prompt_template_falls_back_to_default():
    assert LLMJudge(prompt_template="").fingerprint() == LLMJudge().fingerprint()


def test_custom_prompt_changes_fingerprint():
    assert LLMJudge(prompt_template="A").fingerprint() != LLMJudge(
        prompt_template="B"
    ).fingerprint()
