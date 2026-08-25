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


class _AuditCaptureAdapter(_CaptureAdapter):
    async def fetch_literature_audits(self, mme_session_id: str) -> list[dict]:
        return []


class _ResponsePreferenceContextAdapter(_CaptureAdapter):
    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.requests.append(req)
        return ChatResponse(
            reply="先说结论：指标需要继续观察。下面说明数据依据。",
            raw={
                "evaluation_context": {
                    "sessionId": "cx-session-preference",
                    "enableSystemPrompt": True,
                    "injectedContext": {
                        "initializedModules": {"responsePreferences": 1},
                    },
                    "responsePreference": {
                        "status": "success",
                        "configuredCount": 1,
                        "loaded": True,
                        "effective": True,
                    },
                }
            },
        )


def test_runner_passes_same_initial_state_through_multiturn_metadata() -> None:
    case = TestCase.model_validate(
        {
            "schema_version": "2.0",
            "sample_id": "memory_multi_turn",
            "scenario": "长期记忆",
            "level": "L2",
            "initial_state": {
                "user_profile": {"昵称": "小橙", "current_concern": "乳腺结节随访"},
                "Timeline": [
                    {
                        "睡前习惯": "睡前听十分钟轻音乐更容易入睡",
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
    assert first["user_profile"]["facts"]["昵称"] == "小橙"
    assert first["user_profile"]["current_concern"] == "breast_tumor"
    assert first["user_profile"]["facts"]["当前关注"] == "乳腺结节随访"
    assert first["long_term_memories"][0]["label"] == "睡前习惯"


def test_runner_passes_resolved_turn_images_to_adapter() -> None:
    case = TestCase.model_validate(
        {
            "schema_version": "2.0",
            "sample_id": "image_case",
            "scenario": "报告解读",
            "level": "L2",
            "turns": [
                {
                    "role": "user",
                    "content": "请解读图片中的报告",
                    "images": ["images/case-001-1.jpg"],
                }
            ],
            "evaluation": {},
        }
    )
    case.turns[0].attach_image_data_urls(["data:image/jpeg;base64,aGVsbG8="])
    adapter = _CaptureAdapter()

    trace = asyncio.run(_run_one(case, adapter, timeout_s=5, retry=0))

    assert trace.error is None
    assert adapter.requests[0].images == ["data:image/jpeg;base64,aGVsbG8="]


def test_runner_marks_successful_empty_literature_audit_as_fetched() -> None:
    case = TestCase.model_validate(
        {
            "schema_version": "2.0",
            "sample_id": "empty_audit_case",
            "scenario": "医学文献 RAG",
            "level": "L2",
            "turns": [{"role": "user", "content": "普通咨询"}],
            "evaluation": {},
        }
    )

    trace = asyncio.run(_run_one(case, _AuditCaptureAdapter(), timeout_s=5, retry=0))

    assert trace.cx_literature_audits == []
    assert trace.cx_literature_audit_fetched is True


def test_runner_records_actual_response_preference_runtime_status() -> None:
    case = TestCase.model_validate(
        {
            "schema_version": "2.1",
            "sample_id": "response_preference_runtime",
            "scenario": "回复偏好",
            "level": "L2",
            "initial_state": {
                "response_preferences": [
                    {"preference": "先给结论，再说明数据依据", "basis": "用户明确表达"}
                ]
            },
            "turns": [{"role": "user", "content": "这次检查结果怎么样？"}],
            "evaluation": {},
        }
    )

    trace = asyncio.run(
        _run_one(case, _ResponsePreferenceContextAdapter(), timeout_s=5, retry=0)
    )

    assert trace.evaluation_identity["system_prompt_enabled"] is True
    assert trace.evaluation_identity["injected_context"] == {
        "initializedModules": {"responsePreferences": 1}
    }
    assert trace.evaluation_identity["response_preference"] == {
        "status": "success",
        "configuredCount": 1,
        "loaded": True,
        "effective": True,
    }
