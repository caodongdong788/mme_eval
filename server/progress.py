"""评测进度观察者（实现 medeval.service.ProgressObserver 协议）。

JobRunner 为每个运行中的 run 持有一个 ``InMemoryProgress``，评测编排通过 phase 事件上报，
前端轮询 ``snapshot()`` 渲染进度条。phase key：run / judge_det / judge_llm / judge_sp。
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from medeval.models import CaseResult


CaseCompleteCallback = Callable[["CaseResult"], Awaitable[None] | None]

_PHASE_LABELS = {
    "run": "调用 chatbot",
    "judge_det": "判分（确定性）",
    "judge_llm": "判分（LLM）",
    "judge_sp": "判分（得分点）",
}


class InMemoryProgress:
    """内存进度：记录各 phase 的 total/done 与当前 phase。"""

    def __init__(self) -> None:
        self.phases: dict[str, dict[str, Any]] = {}
        self.current: str | None = None
        self._case_complete_callback: CaseCompleteCallback | None = None
        # 用例级进度与底层调用/判分 phase 分开维护：一个 Case 的多轮对话和
        # 多个 Judge 都完成后才计为 1，适合批量重新评测在界面上展示。
        self._case_total = 0
        self._case_done = 0
        # 重新评测时按 sample_id 记录每个 Case 的可展示状态。普通评测无需
        # 声明这些状态，保持原来的轻量进度语义。
        self._case_states: dict[str, dict[str, Any]] = {}
        # 开跑前声明的全部阶段总量之和；用于全局单调百分比（None=未声明，回退当前阶段口径）。
        self._plan_total: int | None = None

    def set_case_complete_callback(
        self, callback: CaseCompleteCallback | None
    ) -> None:
        """注册单条用例完成回调；平台用它增量落库，CLI/SDK 可不注册。"""
        self._case_complete_callback = callback

    def set_case_total(self, total: int) -> None:
        """声明本次任务实际要完成的用例数。"""
        self._case_total = max(0, int(total))
        self._case_done = min(self._case_done, self._case_total)

    def set_case_ids(self, sample_ids: Iterable[str]) -> None:
        """声明本次重评的 Case 范围，并初始化逐条进度。"""
        ids = list(dict.fromkeys(str(sample_id) for sample_id in sample_ids))
        self._case_total = len(ids)
        self._case_done = 0
        self._case_states = {
            sample_id: {"status": "queued", "percent": 0}
            for sample_id in ids
        }

    def case_started(self, sample_id: str) -> None:
        """Case 已拿到执行槽位，开始调用 Agent / Judge。"""
        state = self._case_states.get(sample_id)
        if state is not None and state.get("status") != "completed":
            state.update({"status": "running", "percent": max(1, int(state.get("percent", 0)))})

    async def case_completed(self, result: "CaseResult") -> None:
        """在一条用例完成 N 次判分并折叠后通知平台。"""
        if self._case_total:
            self._case_done = min(self._case_done + 1, self._case_total)
        else:
            self._case_done += 1
        sample_id = getattr(getattr(result, "case", None), "sample_id", None)
        state = self._case_states.get(sample_id) if sample_id else None
        if state is not None:
            state.update({"status": "completed", "percent": 100})
        if self._case_complete_callback is None:
            return
        pending = self._case_complete_callback(result)
        if inspect.isawaitable(pending):
            await pending

    def plan_phases(self, phases: Iterable[tuple[str, str, int]]) -> None:
        """开跑前一次性声明完整阶段计划（key, label, total），固定全局分母。"""
        total = sum(int(t) for _key, _label, t in phases)
        self._plan_total = total if total > 0 else None

    def start_phase(self, key: str, label: str, total: int) -> None:
        self.phases[key] = {"label": label or _PHASE_LABELS.get(key, key), "total": total, "done": 0}
        self.current = key

    def advance(self, key: str, n: int = 1) -> None:
        phase = self.phases.get(key)
        if phase is not None:
            phase["done"] = phase["done"] + n

    def snapshot(self) -> dict[str, Any]:
        """前端可消费的进度快照。"""
        cur = self.phases.get(self.current) if self.current else None
        if self._plan_total:
            # 全局累计：Σ各已开始阶段 done / Σ全阶段 total —— 跨阶段单调不回退。
            done_sum = sum(p["done"] for p in self.phases.values())
            percent = round(min(done_sum / self._plan_total, 1.0) * 100, 1)
        else:
            # 向后兼容：未声明计划时仍按当前阶段口径。
            percent = 0.0
            if cur and cur["total"]:
                percent = round(min(cur["done"] / cur["total"], 1.0) * 100, 1)
        return {
            "current": self.current,
            "current_label": cur["label"] if cur else "",
            "done": cur["done"] if cur else 0,
            "total": cur["total"] if cur else 0,
            "percent": percent,
            "phases": {k: dict(v) for k, v in self.phases.items()},
            "case_done": self._case_done,
            "case_total": self._case_total,
            "case_states": {sample_id: dict(state) for sample_id, state in self._case_states.items()},
        }
