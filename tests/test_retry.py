"""统一退避/重试单测（change 2026-06-02-unify-retry-backoff）。

覆盖 medeval/retry.py：
  - backoff_delay 单调递增、被 max_delay 封顶、jitter 区间
  - retry_async：retryable 重试后成功 / 非 retryable 立即抛 / 达上限抛最后异常 / on_retry & sleep 调用
"""

from __future__ import annotations

import asyncio

import pytest

from medeval.retry import backoff_delay, retry_async


# --- backoff_delay ---------------------------------------------------------


def test_backoff_delay_monotonic_no_jitter():
    seq = [backoff_delay(i, base=5.0, factor=2.0, max_delay=40.0) for i in range(6)]
    assert seq == [5.0, 10.0, 20.0, 40.0, 40.0, 40.0]  # 第3次起被 40 封顶


def test_backoff_delay_base_zero():
    assert backoff_delay(0, base=0.0, factor=2.0, max_delay=40.0) == 0.0
    assert backoff_delay(3, base=0.0, factor=2.0, max_delay=40.0) == 0.0


def test_backoff_delay_jitter_within_range():
    for _ in range(50):
        d = backoff_delay(0, base=5.0, factor=2.0, max_delay=40.0, jitter=2.0)
        assert 5.0 <= d <= 7.0


# --- retry_async -----------------------------------------------------------


def _collecting_sleep(store: list[float]):
    async def _sleep(s):
        store.append(s)
    return _sleep


def test_retry_async_retries_then_succeeds():
    sleeps: list[float] = []
    calls = {"n": 0}

    async def fn():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise ValueError("transient")
        return "ok"

    out = asyncio.run(
        retry_async(
            fn,
            max_retries=3,
            retryable=lambda e: isinstance(e, ValueError),
            base=5.0,
            factor=2.0,
            max_delay=40.0,
            sleep=_collecting_sleep(sleeps),
        )
    )
    assert out == "ok"
    assert calls["n"] == 3
    assert sleeps == [5.0, 10.0]  # 退避两次，按 backoff_delay


def test_retry_async_non_retryable_raises_immediately():
    sleeps: list[float] = []

    async def fn():
        raise KeyError("nope")

    with pytest.raises(KeyError):
        asyncio.run(
            retry_async(
                fn,
                max_retries=3,
                retryable=lambda e: isinstance(e, ValueError),
                base=5.0,
                max_delay=40.0,
                sleep=_collecting_sleep(sleeps),
            )
        )
    assert sleeps == []  # 非 retryable，不退避


def test_retry_async_raises_after_max_retries():
    sleeps: list[float] = []
    calls = {"n": 0}

    async def fn():
        calls["n"] += 1
        raise ValueError("always")

    with pytest.raises(ValueError):
        asyncio.run(
            retry_async(
                fn,
                max_retries=2,
                retryable=lambda e: True,
                base=1.0,
                max_delay=10.0,
                sleep=_collecting_sleep(sleeps),
            )
        )
    assert calls["n"] == 3  # 初始 + 2 retries
    assert len(sleeps) == 2


def test_retry_async_on_retry_callback():
    events: list[tuple[int, float]] = []

    async def fn():
        if len(events) < 1:
            raise ValueError("x")
        return 1

    asyncio.run(
        retry_async(
            fn,
            max_retries=3,
            retryable=lambda e: True,
            base=2.0,
            max_delay=40.0,
            on_retry=lambda attempt, exc, delay: events.append((attempt, delay)),
            sleep=_collecting_sleep([]),
        )
    )
    assert events == [(0, 2.0)]
