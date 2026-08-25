from __future__ import annotations

import asyncio

from medeval.judges.model_comparison_dimension import ModelComparisonDimensionJudge
from medeval.models import ChatMessage, ConversationTrace, TestCase
from medeval.scoring_standards import MODEL_COMPARISON_DIMENSIONS
from tests.test_v2_case_schema import raw_case


class _Backend:
    def __init__(self) -> None:
        self.prompt = ""

    async def chat_json(self, model: str, prompt: str, temperature: float, **kwargs):
        self.prompt = prompt
        return {
            "scores": {item.key: 5 for item in MODEL_COMPARISON_DIMENSIONS},
            "reasons": {item.key: "满足" for item in MODEL_COMPARISON_DIMENSIONS},
            "assertions": {
                "semantic_followup": {
                    "passed": True,
                    "reason": "已说明复查及其目的",
                    "evidence": ["建议复查血常规，用于确认当前治疗是否安全。"],
                }
            },
        }


def test_model_comparison_verifies_semantic_answer_requirement() -> None:
    data = raw_case()
    data["evaluation"]["assertions"] = [
        {
            "id": "semantic_followup",
            "type": "transcript",
            "description": "说明复查及其目的",
            "contains": "提醒用户复查血常规，并说明用于评估治疗安全性",
            "scope": "assistant_final",
            "match_mode": "semantic",
            "model_comparison_dimensions": ["instruction_following"],
            "model_comparison_deduction": 1,
        }
    ]
    case = TestCase.model_validate(data)
    trace = ConversationTrace(
        messages=[
            ChatMessage(
                role="assistant",
                content="建议复查血常规，用于确认当前治疗是否安全。",
            )
        ]
    )
    backend = _Backend()
    judge = ModelComparisonDimensionJudge(enabled=False)
    judge.enabled = True
    judge._backend = backend  # type: ignore[assignment]

    verdicts = asyncio.run(judge.judge(case, trace))

    assertion = next(item for item in verdicts if item.name == "assertion.semantic_followup")
    assert assertion.passed is True
    assert assertion.evidence == ["建议复查血常规，用于确认当前治疗是否安全。"]
    assert "semantic_followup" in backend.prompt
    assert "不要求逐字复述" in backend.prompt
