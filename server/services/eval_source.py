"""从源 run 目录加载冻结用例与留痕。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from medeval import trace_store
from medeval.models import RunReport

from ..benchmarks import load_benchmark_cases
from ..db import session_scope
from ..models_db import Benchmark, EvalRun
from ..settings import Settings
from .eval_artifacts import read_run_plan


def load_source_run(
    settings: Settings, source_run_id: int
) -> tuple[str, int | None, dict[str, Any], dict[str, Any]]:
    with session_scope() as session:
        src = session.get(EvalRun, source_run_id)
        if src is None:
            raise ValueError(f"源 run {source_run_id} 不存在")
        return (
            src.run_slug,
            src.benchmark_id,
            dict(src.judge_overrides or {}),
            dict(src.adapter_overrides or {}),
        )


def frozen_cases_and_traces(src_dir: Path, *, require_traces: bool):
    report_json = src_dir / "report.json"
    if not report_json.is_file():
        raise ValueError(f"源 run 缺 {report_json.name}，无法重判/续跑")
    prev = RunReport.model_validate_json(report_json.read_text(encoding="utf-8"))
    cases = [r.case for r in prev.results]
    if not cases:
        raise ValueError("源 run 无用例结果")
    n_runs = prev.n_runs or 1

    bundle = trace_store.read_traces(src_dir)
    if bundle is not None:
        per_case_traces = bundle.per_case_traces(cases, n_runs)
    elif require_traces and n_runs > 1:
        raise ValueError(
            f"源 run 缺 traces.jsonl.gz 且 n_runs={n_runs}>1，留痕不足以重做 majority voting"
        )
    else:
        per_case_traces = [[r.trace] for r in prev.results]
    return cases, per_case_traces, n_runs


def resume_cases_and_traces(src_dir: Path, settings: Settings, bm_id: int | None):
    if (src_dir / "report.json").is_file():
        return frozen_cases_and_traces(src_dir, require_traces=False)

    bundle = trace_store.read_traces(src_dir)
    if bundle is None:
        raise ValueError("源 run 既无 report.json 也无可复用留痕，无法续跑")
    if bm_id is None:
        raise ValueError("源 run 未关联 benchmark，无法重建用例集续跑")

    from .. import eval_job as ej

    with session_scope() as session:
        bm = session.get(Benchmark, bm_id)
        if bm is None:
            raise ValueError(f"源 run 的 benchmark {bm_id} 已不存在，无法续跑")
        all_cases = ej.load_benchmark_cases(bm, settings=settings)

    plan = read_run_plan(src_dir)
    if plan and plan.get("sample_ids"):
        order = {sid: i for i, sid in enumerate(plan["sample_ids"])}
        cases = sorted(
            [c for c in all_cases if c.sample_id in order],
            key=lambda c: order[c.sample_id],
        )
    else:
        cases = list(all_cases)

    n_runs = int((plan or {}).get("n_runs") or bundle.meta.get("n_runs") or 1)
    per_case_traces = bundle.per_case_traces(cases, n_runs)
    return cases, per_case_traces, n_runs
