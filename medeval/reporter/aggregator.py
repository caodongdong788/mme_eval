"""把一批 CaseResult 聚合成 RunReport（含分维度切片）。"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from ..models import CaseResult, RunReport
from .scoring import apply_grading, grading_summary
from .stats import bootstrap_ci
from .token_cost import token_cost_from_counts


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """最近秩法 percentile（pct ∈ [0,1]）。空列表由调用方保证不传入。"""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = max(0, min(len(sorted_vals) - 1, round(pct * (len(sorted_vals) - 1))))
    return sorted_vals[rank]


def _latency_summary(results: list[CaseResult]) -> dict[str, Any]:
    """跨用例聚合会话延迟（仅记录、不计分）。过滤代表性 trace 报错的用例。"""
    vals: list[float] = []
    for r in results:
        if r.trace.error:
            continue  # 错误 run 不计入延迟聚合
        if r.per_run_latency_ms:
            vals.extend(r.per_run_latency_ms)
        elif r.trace.duration_ms:
            vals.append(float(r.trace.duration_ms))
    if not vals:
        return {}
    vals.sort()
    return {
        "count": len(vals),
        "avg_ms": sum(vals) / len(vals),
        "median_ms": statistics.median(vals),
        "p90_ms": _percentile(vals, 0.9),
        "max_ms": vals[-1],
    }


def _token_summary(
    results: list[CaseResult], pricing: dict[str, Any] | None = None
) -> dict[str, Any]:
    """跨用例聚合 token 用量与（配置单价时的）成本（仅观测、不计分）。

    口径与 ``_latency_summary`` 一致：过滤代表性 trace 报错的用例。逐 run token 取
    ``CaseResult.per_run_tokens``（含错误 run，这里再过滤）。仅统计被测 bot，不含 judge 模型。

    ``pricing``（来自 ``config_snapshot["cost"]``）的 input/output 单价均 >0 时才折算 cost，
    否则只出 token、不出 cost（报告层据此显示 N/A）。
    """
    prompt_total = 0
    completion_total = 0
    token_total = 0
    count = 0
    for r in results:
        if r.trace.error:
            continue  # 错误 run 不计入聚合
        # 逐 run token（与 per_run_latency_ms 对仗）；缺失则回退到代表性 trace 求和
        per_run = r.per_run_tokens or [
            sum(int(u.get("total_tokens", 0)) for u in r.trace.turn_token_usage)
        ]
        # 逐轮 prompt/completion 拆分仅代表性 trace 有，按其比例不可靠，故直接逐轮累加
        for u in r.trace.turn_token_usage:
            prompt_total += int(u.get("prompt_tokens", 0))
            completion_total += int(u.get("completion_tokens", 0))
        for t in per_run:
            token_total += int(t)
            count += 1
    if token_total == 0 and prompt_total == 0 and completion_total == 0:
        return {}
    summary: dict[str, Any] = {
        "count": count,
        "total_prompt_tokens": prompt_total,
        "total_completion_tokens": completion_total,
        "total_tokens": token_total,
        "avg_tokens_per_run": (token_total / count) if count else 0.0,
    }
    cost = token_cost_from_counts(prompt_total, completion_total, pricing)
    if cost is not None:
        summary["cost"] = cost
        summary["currency"] = (pricing or {}).get("currency", "USD")
        summary["cost_per_run"] = (cost / count) if count else 0.0
    return summary


def _bump(d: dict, key: str, passed: bool) -> None:
    bucket = d.setdefault(key, {"total": 0, "passed": 0, "hard_failed": 0})
    bucket["total"] += 1
    if passed:
        bucket["passed"] += 1


def build_report(
    run_name: str,
    results: list[CaseResult],
    adapter_type: str,
    config_snapshot: dict[str, Any] | None = None,
    description: str = "",
    started_at: datetime | None = None,
    n_runs: int = 1,
) -> RunReport:
    report = RunReport(
        run_name=run_name,
        description=description,
        adapter_type=adapter_type,
        config_snapshot=config_snapshot or {},
        results=results,
        total=len(results),
        started_at=started_at or datetime.utcnow(),
        finished_at=datetime.utcnow(),
        n_runs=n_runs,
    )
    # 评级是报告层叠加产物：先就地写入各 CaseResult 的维度分/综合分/评级，
    # 并按 profile pass_rule + majority gate_passed 写 release_passed，再聚合整体分布。
    # 权重/阈值取自 config_snapshot.scoring。
    apply_grading(results, (config_snapshot or {}).get("scoring"))
    tag_counter: Counter[str] = Counter()
    fp_collector: dict[str, set[str]] = defaultdict(set)
    stability_counter: Counter[str] = Counter()
    guideline_rates: list[float] = []
    for r in results:
        if r.guideline_match_rate is not None:
            guideline_rates.append(r.guideline_match_rate)
        if r.release_passed:
            report.passed += 1
        if not r.hard_gate_passed:
            report.hard_gate_failed += 1
        _bump(report.by_level, r.case.level.value, r.release_passed)
        _bump(report.by_scenario, r.case.scenario, r.release_passed)
        if not r.hard_gate_passed:
            report.by_level[r.case.level.value]["hard_failed"] += 1
        for tag in r.failure_tags:
            tag_counter[tag] += 1
        for v in r.verdicts:
            if not v.judge_fingerprint:
                continue
            judge_name = v.name.split(".", 1)[0]
            fp_collector[judge_name].add(v.judge_fingerprint)
        stability_counter[r.stability] += 1
    report.failure_tag_counter = dict(tag_counter.most_common())
    report.judge_fingerprints = {
        name: ("/".join(sorted(fps)) if len(fps) > 1 else next(iter(fps)))
        for name, fps in fp_collector.items()
    }
    # 三态分布始终包含三个 key（即使某态计数为 0）便于报告渲染稳定取值
    report.stability_distribution = {
        "stable_pass": stability_counter.get("stable_pass", 0),
        "flaky": stability_counter.get("flaky", 0),
        "stable_fail": stability_counter.get("stable_fail", 0),
    }
    # 指南匹配率聚合（macro 平均，仅统计带锚点得分点的用例）。仅度量、不否决。
    if guideline_rates:
        report.guideline_match = {
            "cases_with_guideline": len(guideline_rates),
            "avg_match_rate": sum(guideline_rates) / len(guideline_rates),
        }
    report.latency_summary = _latency_summary(results)
    report.token_summary = _token_summary(results, (config_snapshot or {}).get("cost"))
    report.grading = grading_summary(results)
    # 通过率 bootstrap 置信区间（基于 release_passed，仅统计度量、不影响判分）。
    # 配置缺省（如 SDK/测试直接调 build_report）时按默认开启；可经 run.stats 关闭/调参。
    stats_cfg = ((config_snapshot or {}).get("run") or {}).get("stats") or {}
    if stats_cfg.get("enabled", True) and results:
        report.pass_rate_ci = bootstrap_ci(
            [r.release_passed for r in results],
            n_resamples=int(stats_cfg.get("bootstrap_resamples", 1000)),
            confidence=float(stats_cfg.get("confidence", 0.95)),
            seed=stats_cfg.get("seed", 0),
        )
    return report
