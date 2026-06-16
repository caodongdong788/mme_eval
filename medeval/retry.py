"""统一的异步指数退避重试 —— 退避数学的单一真值源。

参见 OpenSpec change ``2026-06-02-unify-retry-backoff``。

被测 bot 调用（``runner/executor.py``）与 LLM 判官后端（``judges/llm_backend.py``）
原先各写一套退避；这里收敛成一处：

  * ``backoff_delay``：纯函数，给定第几次重试算等待秒数。
  * ``retry_async``：异常驱动的通用重试（fn 抛 retryable 异常即按退避重试）。

executor 的失败是「值驱动」（``ChatResponse.error``）与「异常驱动」混合，结构上保留
自己的循环，仅复用 ``backoff_delay`` 计算等待，不套 ``retry_async``。
"""

from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


def backoff_delay(
    attempt: int,
    *,
    base: float,
    factor: float = 2.0,
    max_delay: float,
    jitter: float = 0.0,
) -> float:
    """第 ``attempt`` 次（0-indexed）重试前的等待秒数。

    ``min(max_delay, base * factor**attempt)``，再加 ``U(0, jitter)`` 的抖动。
    ``base<=0`` 时返回 0（加抖动）——调用方据此决定是否完全跳过 sleep。
    """
    raw = base * (factor ** attempt)
    delay = min(max_delay, raw)
    if jitter:
        delay += random.uniform(0, jitter)
    return delay


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    retryable: Callable[[BaseException], bool],
    base: float,
    factor: float = 2.0,
    max_delay: float,
    jitter: float = 0.0,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
    delay_for: Callable[[int, BaseException], float | None] | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> T:
    """异常驱动的指数退避重试。

    ``fn`` 是无参 async 工厂；``retryable(exc) -> bool`` 决定某异常是否值得重试。
    最多额外重试 ``max_retries`` 次（总尝试 ``max_retries+1``）。非 retryable 异常
    或达到上限 → 原样抛出。``sleep`` 缺省运行时取 ``asyncio.sleep``（尊重 monkeypatch）。
    """
    _sleep = sleep or asyncio.sleep
    attempt = 0
    while True:
        try:
            return await fn()
        except BaseException as e:  # noqa: BLE001 —— 由 retryable 决定去留
            if not retryable(e) or attempt >= max_retries:
                raise
            delay = backoff_delay(
                attempt, base=base, factor=factor, max_delay=max_delay, jitter=jitter
            )
            if delay_for is not None:
                override = delay_for(attempt, e)
                if override is not None:
                    delay = override
            if on_retry is not None:
                on_retry(attempt, e, delay)
            await _sleep(delay)
            attempt += 1
