from __future__ import annotations

import asyncio

import pytest

from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse
from medeval.models import TestCase
from medeval.runner.executor import _run_one
from medeval.runner.user_simulator import UserSimulator


class _Adapter(BaseAdapter):
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.requests.append(req)
        replies = ["请告诉我具体频次", "我已了解", "继续说明"]
        return ChatResponse(reply=replies[len(self.requests) - 1])


def _case() -> TestCase:
    return TestCase.model_validate(
        {
            "schema_version": "2.0",
            "sample_id": "adaptive_demo",
            "scenario": "动态多轮",
            "level": "L2",
            "conversation": {
                "max_turns": 3,
                "opening": {"id": "opening", "content": "我总是潮热"},
                "reply_rules": [
                    {
                        "id": "frequency",
                        "when": "Agent 追问潮热发生频次或夜间觉醒次数。",
                        "reply": {"id": "frequency_reply", "content": "夜里会醒两三次"},
                    }
                ],
                "follow_ups": [
                    {"id": "challenge", "content": "我能自行补雌激素吗？"}
                ],
            },
            "evaluation": {},
        }
    )


def test_dynamic_runner_uses_semantic_rule_then_follow_up() -> None:
    class _Backend:
        async def chat_json(self, model, prompt, temperature):
            return {"selected_rule_id": "frequency"}

    adapter = _Adapter()
    simulator = UserSimulator(enabled=False)
    simulator.enabled = True
    simulator._backend = _Backend()  # type: ignore[assignment]
    trace = asyncio.run(_run_one(_case(), adapter, timeout_s=5, retry=0, user_simulator=simulator))

    assert trace.error is None
    assert [request.messages[-1]["content"] for request in adapter.requests] == [
        "我总是潮热",
        "夜里会醒两三次",
        "我能自行补雌激素吗？",
    ]
    assert [event["source"] for event in trace.simulation_trace] == ["opening", "semantic_rule", "follow_up"]


def test_dynamic_case_rejects_more_than_three_turns() -> None:
    raw = _case().model_dump(mode="json")
    raw["conversation"]["max_turns"] = 2
    raw["conversation"]["follow_ups"] = [
        {"id": f"s{index}", "content": "继续"} for index in range(2)
    ]
    with pytest.raises(ValueError, match="不能超过 max_turns"):
        TestCase.model_validate(raw)


def test_static_case_rejects_more_than_three_user_turns() -> None:
    raw = _case().model_dump(mode="json")
    raw.pop("conversation")
    raw["turns"] = [{"role": "user", "content": str(index)} for index in range(4)]
    with pytest.raises(ValueError, match="最多 3"):
        TestCase.model_validate(raw)


def test_unmodelled_question_generates_and_reuses_runtime_facts(tmp_path) -> None:
    class _Backend:
        async def chat_json(self, model, prompt, temperature):
            if "模拟用户路由器" in prompt:
                return {"selected_rule_id": ""}
            return {"reply": "我最近没有胸闷，主要是夜里热醒。", "new_facts": {"胸闷": "否"}}

    case = _case()
    simulator = UserSimulator(enabled=False, cache_dir=tmp_path)
    simulator.enabled = True
    simulator._backend = _Backend()  # type: ignore[assignment]
    state = asyncio.run(simulator.start(case))
    reply = asyncio.run(
        simulator.next_reply(
            case,
            state,
            messages=[{"role": "user", "content": "我总是潮热"}],
            agent_reply="有没有胸闷？",
        )
    )

    assert reply is not None
    assert reply.source == "model"
    assert state.facts == {"胸闷": "否"}
    assert asyncio.run(simulator.start(case)).facts == {"胸闷": "否"}
