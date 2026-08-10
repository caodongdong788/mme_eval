"""cx-agent 隔离评测账号的进程内公平限流器。

实际账号租约仍由 cx-agent 服务发放；本模块只在发起租约前做全局排队，确保同一个
MME 进程中的多条评测不会把普通/长期记忆账号池同时耗尽。每个 asyncio 事件循环
维护独立状态，避免测试或短命 CLI 进程之间互相污染。
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal


AccountPool = Literal["stateless", "stateful"]
_POOLS: tuple[AccountPool, ...] = ("stateless", "stateful")


@dataclass
class _PoolState:
    capacity: int
    per_owner_limit: int
    in_use: Counter[str] = field(default_factory=Counter)
    waiters: list[str] = field(default_factory=list)
    last_granted_owner: str | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)

    @property
    def used(self) -> int:
        return sum(self.in_use.values())

    def _next_owner(self) -> str | None:
        eligible: list[str] = []
        for owner in self.waiters:
            if owner not in eligible and self.in_use[owner] < self.per_owner_limit:
                eligible.append(owner)
        if not eligible:
            return None
        if self.last_granted_owner in eligible and len(eligible) > 1:
            position = eligible.index(self.last_granted_owner)
            return eligible[(position + 1) % len(eligible)]
        return eligible[0]

    def queue_position(self, owner: str) -> int | None:
        owners: list[str] = []
        for item in self.waiters:
            if item not in owners:
                owners.append(item)
        if owner not in owners:
            return None

        # 已达到单任务占用上限的请求仍然是真正的等待者，不能在状态接口中被
        # 误报成「未排队」。它会排在当前可获分配的任务之后，等本任务归还一个
        # 名额后再参加下一轮分配。
        eligible = [item for item in owners if self.in_use[item] < self.per_owner_limit]
        if owner not in eligible:
            return len(eligible) + owners.index(owner) + 1
        if self.last_granted_owner in eligible and len(eligible) > 1:
            position = eligible.index(self.last_granted_owner)
            ordered = eligible[position + 1 :] + eligible[: position + 1]
        else:
            ordered = eligible
        return ordered.index(owner) + 1


@dataclass
class _LoopState:
    pools: dict[AccountPool, _PoolState]


class EvaluationAccountLimiter:
    """同一事件循环内的两个账号池限流与轮转调度。"""

    def __init__(self) -> None:
        self._capacities: dict[AccountPool, int] = {"stateless": 8, "stateful": 8}
        self._per_owner_limit = 2
        self._states: dict[asyncio.AbstractEventLoop, _LoopState] = {}
        self._latest_state: _LoopState | None = None

    def configure(
        self,
        *,
        stateless_capacity: int,
        stateful_capacity: int,
        per_owner_limit: int,
    ) -> None:
        """更新后续新事件循环的容量配置。

        已有运行中的事件循环继续使用启动时容量，避免中途缩容造成已占用 token
        无法归还。生产服务的 config 在启动期固定，因此不会出现配置漂移。
        """
        self._capacities = {
            "stateless": max(1, int(stateless_capacity)),
            "stateful": max(1, int(stateful_capacity)),
        }
        self._per_owner_limit = max(1, int(per_owner_limit))

    def _state(self) -> _LoopState:
        loop = asyncio.get_running_loop()
        state = self._states.get(loop)
        if state is None:
            state = _LoopState(
                pools={
                    pool: _PoolState(
                        capacity=self._capacities[pool],
                        per_owner_limit=self._per_owner_limit,
                    )
                    for pool in _POOLS
                }
            )
            self._states[loop] = state
        self._latest_state = state
        return state

    async def acquire(self, pool: AccountPool, owner: str) -> None:
        state = self._state().pools[pool]
        owner = owner or "unknown"
        async with state.condition:
            state.waiters.append(owner)
            try:
                while state.used >= state.capacity or state._next_owner() != owner:
                    await state.condition.wait()
                state.waiters.remove(owner)
                state.in_use[owner] += 1
                state.last_granted_owner = owner
                state.condition.notify_all()
            except BaseException:
                if owner in state.waiters:
                    state.waiters.remove(owner)
                    state.condition.notify_all()
                raise

    async def release(self, pool: AccountPool, owner: str) -> None:
        state = self._state().pools[pool]
        owner = owner or "unknown"
        async with state.condition:
            if state.in_use[owner] > 1:
                state.in_use[owner] -= 1
            else:
                state.in_use.pop(owner, None)
            state.condition.notify_all()

    def snapshot(self, owner: str) -> dict:
        """为平台状态接口输出 owner 在两类账号池的实时排队信息。"""
        state = self._latest_state
        if state is None:
            return {"enabled": False, "waiting_for_accounts": False, "pools": {}}
        pools: dict[str, dict] = {}
        waiting = False
        positions: list[int] = []
        for key, pool in state.pools.items():
            position = pool.queue_position(owner)
            is_waiting = owner in pool.waiters
            waiting = waiting or is_waiting
            if position is not None:
                positions.append(position)
            pools[key] = {
                "capacity": pool.capacity,
                "in_use": pool.used,
                "queued": len(pool.waiters),
                "owner_in_use": pool.in_use.get(owner, 0),
                "owner_waiting": is_waiting,
                "owner_queue_position": position,
            }
        return {
            "enabled": True,
            "waiting_for_accounts": waiting,
            "queue_position": min(positions) if positions else None,
            "pools": pools,
        }

    def reset_for_tests(self) -> None:
        self._states.clear()
        self._latest_state = None
        self._capacities = {"stateless": 8, "stateful": 8}
        self._per_owner_limit = 2


evaluation_account_limiter = EvaluationAccountLimiter()


def account_queue_snapshot(owner: str) -> dict:
    return evaluation_account_limiter.snapshot(owner)


def reset_account_limiter_for_tests() -> None:
    evaluation_account_limiter.reset_for_tests()
