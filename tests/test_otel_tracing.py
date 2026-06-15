"""可选 OTel tracing 单测（enhance-eval-engine Phase 2）。

覆盖：
  - 关闭时 span() 为 no-op（yield None），不报错、不产生 span
  - 未启用时主链路（run_cases）正常、零 span
  - 启用（内存 exporter）时：手工 span 记录 + 属性写入
  - 启用时 run_cases 每个 user turn 产生一个 adapter.chat span
  - configure_tracing(enabled=False) 与未装 otel 时不抛错
"""

from __future__ import annotations

import asyncio

import pytest

from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse
from medeval.models import Level, TestCase, Turn
from medeval.observability import tracing
from medeval.runner import run_cases


class _Adapter(BaseAdapter):
    name = "stub"

    async def chat(self, req: ChatRequest) -> ChatResponse:
        return ChatResponse(reply="本回答仅供参考", raw={})

    async def close(self) -> None:
        pass


def _case(sid: str = "a", turns: int = 1) -> TestCase:
    return TestCase(
        sample_id=sid,
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content=f"q{i}") for i in range(turns)],
    )


def teardown_function() -> None:
    tracing.reset_for_tests()


# ---------------------------------------------------------------------------
# 关闭路径（无需 otel）


def test_span_noop_when_disabled():
    tracing.reset_for_tests()
    with tracing.span("x", a=1, b=None) as sp:
        assert sp is None  # no-op，yield None


def test_configure_disabled_returns_false():
    assert tracing.configure_tracing(enabled=False) is False


def test_run_cases_works_without_tracing():
    tracing.reset_for_tests()
    traces = asyncio.run(run_cases([_case(turns=2)], _Adapter(), concurrency=1, retry=0))
    assert len(traces[0][0].turn_latencies_ms) == 2


# ---------------------------------------------------------------------------
# 启用路径（需要 otel SDK，否则 skip）


def _memory_provider():
    pytest.importorskip("opentelemetry")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_span_records_with_attributes():
    provider, exporter = _memory_provider()
    tracing.set_tracer_for_tests(provider.get_tracer("test"))
    with tracing.span("phase.run", n_cases=3):
        with tracing.span("adapter.chat", sample_id="bc_001", turn_index=0, skip=None):
            pass
    spans = exporter.get_finished_spans()
    names = {s.name for s in spans}
    assert {"phase.run", "adapter.chat"} <= names
    chat = next(s for s in spans if s.name == "adapter.chat")
    assert chat.attributes.get("sample_id") == "bc_001"
    assert chat.attributes.get("turn_index") == 0
    assert "skip" not in chat.attributes  # None 属性被跳过


def test_run_cases_emits_adapter_spans_when_enabled():
    provider, exporter = _memory_provider()
    tracing.set_tracer_for_tests(provider.get_tracer("test"))
    asyncio.run(run_cases([_case(turns=3)], _Adapter(), concurrency=1, retry=0))
    chat_spans = [s for s in exporter.get_finished_spans() if s.name == "adapter.chat"]
    assert len(chat_spans) == 3
    assert all(s.attributes.get("sample_id") == "a" for s in chat_spans)
    assert all("latency_ms" in s.attributes for s in chat_spans)
