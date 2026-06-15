"""可选 Langfuse 追踪单测（add-langfuse-bot-tracing）。

覆盖：
  - 关闭时 generation()/conversation() 为 no-op（yield None），不报错
  - configure_langfuse(enabled=False) 返回 False
  - 未装 langfuse 依赖时 configure_langfuse(enabled=True) 静默退化为 no-op
  - 启用（注入 fake client）时：run_cases 每个 user turn 产生一个 generation，
    带 input(messages)/output(reply)/model/usage/latency；每条 case/run 产生会话 span
  - 零侵入不变量：tracing on/off 两次跑，ConversationTrace 完全一致
  - flush()：关闭时 no-op，启用时调用 client.flush
"""

from __future__ import annotations

import asyncio
import sys

import pytest

from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse
from medeval.models import Level, TestCase, Turn
from medeval.observability import langfuse_tracing as lf
from medeval.runner import run_cases


class _Adapter(BaseAdapter):
    name = "stub"
    model = "stub-model"

    async def chat(self, req: ChatRequest) -> ChatResponse:
        return ChatResponse(
            reply="本回答仅供参考",
            raw={"usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}},
        )

    async def close(self) -> None:
        pass


def _case(sid: str = "a", turns: int = 1) -> TestCase:
    return TestCase(
        sample_id=sid,
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content=f"q{i}") for i in range(turns)],
    )


# --- fake Langfuse client（仿 v4 start_as_current_observation 上下文管理器）-----------


class _FakeObs:
    def __init__(self, store, *, as_type, name, input, model, metadata):
        self.record = {
            "as_type": as_type,
            "name": name,
            "input": input,
            "model": model,
            "metadata": dict(metadata or {}),
            "output": None,
            "usage": None,
            "session_id": None,
        }
        store.append(self.record)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def update(self, *, output=None, usage_details=None, metadata=None):
        if output is not None:
            self.record["output"] = output
        if usage_details is not None:
            self.record["usage"] = usage_details
        if metadata:
            self.record["metadata"].update(metadata)

    def update_trace(self, *, session_id=None, name=None):
        if session_id is not None:
            self.record["session_id"] = session_id


class _FakeClient:
    def __init__(self):
        self.observations: list[dict] = []
        self.flushed = 0
        self._trace_seq = 0
        self._current_trace_id: str | None = None

    def start_as_current_observation(
        self, *, as_type="span", name=None, input=None, model=None, metadata=None, **_kw
    ):
        # span 作为一条独立 trace 的根：分配新 trace_id。
        if as_type == "span":
            self._trace_seq += 1
            self._current_trace_id = f"trace-{self._trace_seq}"
        return _FakeObs(
            self.observations,
            as_type=as_type,
            name=name,
            input=input,
            model=model,
            metadata=metadata,
        )

    def get_current_trace_id(self):
        return self._current_trace_id

    def get_trace_url(self, *, trace_id):
        return f"https://lf.example/trace/{trace_id}" if trace_id else None

    def flush(self):
        self.flushed += 1

    def shutdown(self):
        pass


def teardown_function() -> None:
    lf.reset_for_tests()


# ---------------------------------------------------------------------------
# 关闭路径（无需 langfuse）


def test_generation_noop_when_disabled():
    lf.reset_for_tests()
    with lf.generation("adapter.chat", input=[{"role": "user", "content": "q"}]) as gen:
        assert gen is None
    with lf.conversation("conv", sample_id="a") as conv:
        assert conv is None


def test_configure_disabled_returns_false():
    assert lf.configure_langfuse(enabled=False) is False


def test_flush_noop_when_disabled():
    lf.reset_for_tests()
    lf.flush()  # 不报错即可


def test_run_cases_works_without_langfuse():
    lf.reset_for_tests()
    traces = asyncio.run(run_cases([_case(turns=2)], _Adapter(), concurrency=1, retry=0))
    assert len(traces[0][0].turn_latencies_ms) == 2


def test_missing_langfuse_dependency_degrades_to_noop(monkeypatch):
    # 模拟未安装 langfuse：import langfuse 抛错 → configure 返回 False、保持 no-op
    monkeypatch.setitem(sys.modules, "langfuse", None)
    assert lf.configure_langfuse(enabled=True, public_key="pk", secret_key="sk") is False
    with lf.generation("adapter.chat", input=[]) as gen:
        assert gen is None


# ---------------------------------------------------------------------------
# 启用路径（注入 fake client，无需真实 langfuse）


def test_run_cases_emits_generations_when_enabled():
    client = _FakeClient()
    lf.set_client_for_tests(client)
    asyncio.run(
        run_cases([_case(turns=3)], _Adapter(), concurrency=1, retry=0, run_name="run-xyz")
    )

    gens = [o for o in client.observations if o["as_type"] == "generation"]
    convs = [o for o in client.observations if o["as_type"] == "span"]

    assert len(gens) == 3
    assert len(convs) == 1  # 每条 case/run 一条独立 trace 的根 span
    assert convs[0]["metadata"].get("sample_id") == "a"
    assert convs[0]["name"] == "case:a"
    assert convs[0]["session_id"] == "run-xyz"  # 按 run_name 分组

    for g in gens:
        assert g["output"] == "本回答仅供参考"
        assert g["model"] == "stub-model"
        assert isinstance(g["input"], list) and g["input"][-1]["role"] == "user"
        assert g["usage"]["total_tokens"] == 12
        assert "latency_ms" in g["metadata"]


def test_per_case_trace_url_captured_on_conversation_trace():
    client = _FakeClient()
    lf.set_client_for_tests(client)
    traces = asyncio.run(
        run_cases([_case(turns=2)], _Adapter(), concurrency=1, retry=0, run_name="run-1")
    )
    url = traces[0][0].langfuse_trace_url
    assert url is not None and url.startswith("https://lf.example/trace/")


def test_trace_url_none_when_disabled():
    lf.reset_for_tests()
    traces = asyncio.run(run_cases([_case(turns=1)], _Adapter(), concurrency=1, retry=0))
    assert traces[0][0].langfuse_trace_url is None


def test_tracing_does_not_change_results():
    # 零侵入不变量：on / off 两次跑，ConversationTrace 一致
    lf.reset_for_tests()
    off = asyncio.run(run_cases([_case(turns=3)], _Adapter(), concurrency=1, retry=0))

    lf.set_client_for_tests(_FakeClient())
    on = asyncio.run(run_cases([_case(turns=3)], _Adapter(), concurrency=1, retry=0))

    def _shape(traces):
        t = traces[0][0]
        return (
            [(m.role, m.content) for m in t.messages],
            t.error,
            len(t.turn_latencies_ms),
            t.turn_token_usage,
        )

    assert _shape(off) == _shape(on)


def test_flush_invokes_client_when_enabled():
    client = _FakeClient()
    lf.set_client_for_tests(client)
    lf.flush()
    assert client.flushed == 1
