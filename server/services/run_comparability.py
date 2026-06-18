"""两次 EvalRun 的可比性辅助（benchmark / 判分指纹）。"""

from __future__ import annotations

from typing import Any

from ..models_db import EvalRun


def same_benchmark(run_a: EvalRun, run_b: EvalRun) -> bool:
    return (run_a.benchmark_id or None) == (run_b.benchmark_id or None)


def judge_fingerprints_match(run_a: EvalRun, run_b: EvalRun) -> bool:
    return (run_a.judge_fingerprints or {}) == (run_b.judge_fingerprints or {})


def judge_fingerprint_changes(current: EvalRun, against: EvalRun) -> dict[str, Any]:
    fp_cur = current.judge_fingerprints or {}
    fp_base = against.judge_fingerprints or {}
    return {
        k: {"against": fp_base.get(k), "current": fp_cur.get(k)}
        for k in set(fp_cur) | set(fp_base)
        if fp_cur.get(k) != fp_base.get(k)
    }
