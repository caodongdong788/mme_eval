from __future__ import annotations

import asyncio

from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse
from medeval.models import TestCase
from medeval.runner.executor import _run_one


class _CaptureAdapter(BaseAdapter):
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.requests.append(req)
        return ChatResponse(reply=f"第{len(self.requests)}轮回答")


def test_runner_passes_same_initial_state_through_multiturn_metadata() -> None:
    case = TestCase.model_validate(
        {
            "schema_version": "2.0",
            "sample_id": "memory_multi_turn",
            "scenario": "长期记忆",
            "level": "L2",
            "initial_state": {
                "user_profile": {"nickname": "小橙"},
                "long_term_memories": [
                    {
                        "key": "sleep_preference",
                        "category": "activity",
                        "label": "睡前习惯",
                        "content": "睡前听十分钟轻音乐更容易入睡",
                        "memory_tier": "semantic",
                        "importance": 6,
                    }
                ],
            },
            "turns": [
                {"role": "user", "content": "我之前怎么做更容易睡着？"},
                {"role": "user", "content": "那今晚我应该怎么安排？"},
            ],
            "evaluation": {},
        }
    )
    adapter = _CaptureAdapter()

    trace = asyncio.run(_run_one(case, adapter, timeout_s=5, retry=0))

    assert trace.error is None
    assert len(adapter.requests) == 2
    first = adapter.requests[0].metadata["initial_state"]
    second = adapter.requests[1].metadata["initial_state"]
    assert first == second
    assert first["user_profile"]["nickname"] == "小橙"
    assert first["long_term_memories"][0]["key"] == "sleep_preference"
