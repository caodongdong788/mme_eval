"""N-runs majority voting aggregator.

参见 OpenSpec change ``harden-evaluation-determinism`` / ``decouple-scoring-axes``:
  - 每条 case 跑 N 次后，得到 N 个 ``CaseResult``
  - majority 折叠为单个最终 ``CaseResult``，**基于 judging 层 ``gate_passed`` 口径**
    （非报告层 ``release_passed``）
  - 判定规则：N 奇数时 ≥⌈N/2⌉ 过即过；N 偶数时严格过半（平票算挂）
  - 代表性 trace = 与最终结果一致的最早一次（i 最小）
  - LLM Judge 的调用由上层 cli 控制：先做确定性 judge，再 majority，再代表 trace 跑 LLM
"""

from __future__ import annotations

from typing import Literal

from ..models import CaseResult, ConversationTrace


def trace_total_tokens(trace: ConversationTrace) -> int:
    """一条 trace 的会话总 token = 各轮 turn_token_usage 的 total_tokens 之和。

    空 dict 占位（adapter 未返回 usage 的轮次）记 0。仅观测、不参与判分。
    """
    return sum(int(u.get("total_tokens", 0)) for u in trace.turn_token_usage)


def _is_majority_pass(per_run_gate_passed: list[bool]) -> bool:
    """严格过半。N 偶数平票算挂。"""
    if not per_run_gate_passed:
        return False
    pass_count = sum(1 for p in per_run_gate_passed if p)
    return pass_count * 2 > len(per_run_gate_passed)


def _classify_stability(
    per_run_gate_passed: list[bool],
) -> Literal["stable_pass", "flaky", "stable_fail"]:
    if all(per_run_gate_passed):
        return "stable_pass"
    if not any(per_run_gate_passed):
        return "stable_fail"
    return "flaky"


def fold_n_runs(per_run_results: list[list[CaseResult]]) -> list[CaseResult]:
    """把每条 case 的 N 次 ``CaseResult`` 折叠为单个最终 ``CaseResult``。

    输入：``list[list[CaseResult]]``，外层 = case、内层长度 = N。
    输出：``list[CaseResult]`` 长度等于外层。
    """
    folded: list[CaseResult] = []
    for runs in per_run_results:
        if not runs:
            raise ValueError("fold_n_runs received an empty per-case run list")
        if len(runs) == 1:
            r = runs[0]
            r.n_runs = 1
            r.per_run_gate_passed = [r.gate_passed]
            r.per_run_latency_ms = [float(r.trace.duration_ms)]
            r.per_run_tokens = [trace_total_tokens(r.trace)]
            r.stability = "stable_pass" if r.gate_passed else "stable_fail"
            folded.append(r)
            continue

        per_run_gate_passed = [r.gate_passed for r in runs]
        majority_pass = _is_majority_pass(per_run_gate_passed)
        stability = _classify_stability(per_run_gate_passed)

        # 代表性 trace 选取：先选 gate_passed == majority_pass 的子集，再取最早一次
        candidates = [
            (i, r) for i, r in enumerate(runs) if r.gate_passed == majority_pass
        ]
        # 极端情况：N 全 fail 但 majority_pass=False，candidates 仍非空；
        # 但若 candidates 仍为空（理论上不会发生），退回到第 0 次
        rep_idx, rep = candidates[0] if candidates else (0, runs[0])

        rep.n_runs = len(runs)
        rep.per_run_gate_passed = per_run_gate_passed
        # 收集每次会话总耗时（含错误 run；错误 run 在报告聚合时再过滤）
        rep.per_run_latency_ms = [float(run.trace.duration_ms) for run in runs]
        # 收集每次会话总 token（同上，含错误 run，聚合时再过滤）
        rep.per_run_tokens = [trace_total_tokens(run.trace) for run in runs]
        rep.stability = stability
        # majority 决定最终 gate_passed（报告层 release_passed 由 apply_grading 另算）
        rep.gate_passed = majority_pass
        # hard_gate 保持代表性 run 的值（majority pass 必有一次 hard_gate_passed=True）
        # 若 majority fail，rep 的 hard_gate_passed 反映"为什么挂"
        folded.append(rep)
    return folded
