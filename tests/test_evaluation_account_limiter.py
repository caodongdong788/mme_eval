"""评测账号池的跨任务限流与公平等待。"""

from __future__ import annotations

import asyncio

from medeval.evaluation_account_limiter import (
    account_queue_snapshot,
    evaluation_account_limiter,
    reset_account_limiter_for_tests,
)


def setup_function() -> None:
    reset_account_limiter_for_tests()


def teardown_function() -> None:
    reset_account_limiter_for_tests()


def test_account_exhaustion_waits_instead_of_failing() -> None:
    async def scenario() -> None:
        evaluation_account_limiter.configure(
            stateless_capacity=1,
            stateful_capacity=1,
            per_owner_limit=1,
        )
        await evaluation_account_limiter.acquire("stateless", "run-a")
        waiting = asyncio.create_task(
            evaluation_account_limiter.acquire("stateless", "run-b")
        )
        await asyncio.sleep(0)

        snapshot = account_queue_snapshot("run-b")
        assert snapshot["waiting_for_accounts"] is True
        assert snapshot["queue_position"] == 1
        assert snapshot["pools"]["stateless"]["owner_waiting"] is True

        await evaluation_account_limiter.release("stateless", "run-a")
        await waiting
        assert account_queue_snapshot("run-b")["waiting_for_accounts"] is False
        await evaluation_account_limiter.release("stateless", "run-b")

    asyncio.run(scenario())


def test_one_large_run_cannot_monopolize_account_pool() -> None:
    async def scenario() -> None:
        evaluation_account_limiter.configure(
            stateless_capacity=4,
            stateful_capacity=1,
            per_owner_limit=2,
        )
        await evaluation_account_limiter.acquire("stateless", "large-run")
        await evaluation_account_limiter.acquire("stateless", "large-run")
        third_large = asyncio.create_task(
            evaluation_account_limiter.acquire("stateless", "large-run")
        )
        await asyncio.sleep(0)

        # 即使大任务还有等待请求，也必须给新任务留出自己的并发名额。
        await evaluation_account_limiter.acquire("stateless", "new-run")
        snapshot = account_queue_snapshot("large-run")
        assert snapshot["waiting_for_accounts"] is True
        assert snapshot["pools"]["stateless"]["owner_in_use"] == 2

        await evaluation_account_limiter.release("stateless", "large-run")
        await third_large
        await evaluation_account_limiter.release("stateless", "large-run")
        await evaluation_account_limiter.release("stateless", "large-run")
        await evaluation_account_limiter.release("stateless", "new-run")

    asyncio.run(scenario())
