"""评测进度观察者（实现 medeval.service.ProgressObserver 协议）。

JobRunner 为每个运行中的 run 持有一个 ``InMemoryProgress``，评测编排通过 phase 事件上报，
前端轮询 ``snapshot()`` 渲染进度条。phase key：run / judge_det / judge_llm / judge_sp。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

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
        # 开跑前声明的全部阶段总量之和；用于全局单调百分比（None=未声明，回退当前阶段口径）。
        self._plan_total: int | None = None

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
        }
