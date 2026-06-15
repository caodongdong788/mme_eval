"""executor 重试退避单测（change 2026-06-02-unify-retry-backoff）。

  - retry_backoff_base_s>0：失败重试之间按 backoff_delay 等待
  - retry_backoff_base_s=0（默认）：不插入任何 sleep（行为不变）
"""

from __future__ import annotations

import asyncio

from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse
from medeval.models import Level, TestCase, Turn
from medeval.runner import executor, run_cases


class _FlakyAdapter(BaseAdapter):
    """前 ``fail_times`` 次返回 error，之后成功。"""

    name = "flaky"

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.calls += 1
        if self.calls <= self.fail_times:
            return ChatResponse(reply="", error="transient boom")
        return ChatResponse(reply="ok", raw={})

    async def close(self) -> None:
        pass


def _case() -> TestCase:
    return TestCase(
        sample_id="bk", scenario="t", level=Level.L2,
        turns=[Turn(role="user", content="hi")],
    )


def test_backoff_enabled_sleeps_between_retries(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(s):
        sleeps.append(s)

    # executor 直接调用 asyncio.sleep（全局模块属性），打桩拦截
    monkeypatch.setattr(executor.asyncio, "sleep", fake_sleep)

    adapter = _FlakyAdapter(fail_times=2)
    traces = asyncio.run(
        run_cases(
            [_case()],
            adapter,
            concurrency=1,
            retry=3,
            retry_backoff_base_s=2.0,
            retry_backoff_max_s=40.0,
        )
    )
    assert traces[0][0].error is None  # 第三次成功
    assert adapter.calls == 3
    # 两次失败 → 两次退避：backoff_delay(0)=2, backoff_delay(1)=4
    assert sleeps == [2.0, 4.0]


def test_backoff_disabled_by_default_no_sleep(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(executor.asyncio, "sleep", fake_sleep)

    adapter = _FlakyAdapter(fail_times=2)
    traces = asyncio.run(
        run_cases([_case()], adapter, concurrency=1, retry=3)  # base 默认 0.0
    )
    assert traces[0][0].error is None
    assert adapter.calls == 3
    assert sleeps == []  # 默认不退避，行为不变
