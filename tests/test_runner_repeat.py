"""Test run_cases repeat parameter (change harden-evaluation-determinism)."""

from __future__ import annotations

import asyncio

from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse
from medeval.models import HardGates, Level, RedFlagTriage, TestCase, Turn
from medeval.runner import run_cases


class _RecordingAdapter(BaseAdapter):
    """Records every (session_id, messages) it sees."""

    name = "recording"

    def __init__(self):
        self.calls: list[dict] = []

    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.calls.append(
            {"session_id": req.session_id, "messages": list(req.messages)}
        )
        return ChatResponse(reply=f"reply-{len(self.calls)}", raw={})

    async def close(self) -> None:
        pass


def _case(sid: str) -> TestCase:
    return TestCase(
        sample_id=sid,
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content="hi")],
    )


def test_repeat_default_is_one():
    adapter = _RecordingAdapter()
    traces = asyncio.run(run_cases([_case("a")], adapter, concurrency=1, retry=0))
    assert isinstance(traces, list)
    assert len(traces) == 1
    assert isinstance(traces[0], list)
    assert len(traces[0]) == 1
    # 单次跑 session_id 不带 #run 后缀
    assert "#run" not in adapter.calls[0]["session_id"]


def test_repeat_3_calls_adapter_three_times():
    adapter = _RecordingAdapter()
    traces = asyncio.run(
        run_cases([_case("a")], adapter, concurrency=1, retry=0, repeat=3)
    )
    assert len(traces) == 1
    assert len(traces[0]) == 3
    # 每次的 reply 不同（说明确实跑了 3 次独立 run）
    replies = [t.messages[-1].content for t in traces[0]]
    assert replies == ["reply-1", "reply-2", "reply-3"]


def test_repeat_session_id_distinguishable():
    adapter = _RecordingAdapter()
    asyncio.run(
        run_cases([_case("a")], adapter, concurrency=1, retry=0, repeat=3)
    )
    sids = [c["session_id"] for c in adapter.calls]
    assert len(set(sids)) == 3, f"expected 3 distinct session_ids, got {sids}"
    # 三个 sid 都包含 #run0 / #run1 / #run2
    suffixes = sorted(s.split("#")[-1] for s in sids)
    assert suffixes == ["run0", "run1", "run2"]


def test_repeat_n2_two_cases():
    adapter = _RecordingAdapter()
    traces = asyncio.run(
        run_cases(
            [_case("a"), _case("b")],
            adapter,
            concurrency=2,
            retry=0,
            repeat=2,
        )
    )
    assert len(traces) == 2  # 2 cases
    assert all(len(per_case) == 2 for per_case in traces)
    # adapter 调用总次数 = 2 case × 2 run = 4
    assert len(adapter.calls) == 4


def test_repeat_zero_raises():
    import pytest

    adapter = _RecordingAdapter()
    with pytest.raises(ValueError):
        asyncio.run(run_cases([_case("a")], adapter, repeat=0))


def test_progress_callback_receives_run_index():
    adapter = _RecordingAdapter()
    received: list[tuple[str, int]] = []

    def cb(case, _trace, run_idx):
        received.append((case.sample_id, run_idx))

    asyncio.run(
        run_cases(
            [_case("a"), _case("b")],
            adapter,
            concurrency=1,
            retry=0,
            repeat=2,
            on_progress=cb,
        )
    )
    # 顺序不保证（因为 concurrency 可能并发），但内容必须含全部
    assert sorted(received) == [("a", 0), ("a", 1), ("b", 0), ("b", 1)]


def test_progress_callback_2arg_backward_compat():
    """老的 2 参签名不应抛 TypeError。"""
    adapter = _RecordingAdapter()
    received: list[str] = []

    def cb(case, _trace):  # 只接 2 个参数
        received.append(case.sample_id)

    asyncio.run(
        run_cases(
            [_case("a")],
            adapter,
            concurrency=1,
            retry=0,
            repeat=2,
            on_progress=cb,
        )
    )
    assert received == ["a", "a"]
