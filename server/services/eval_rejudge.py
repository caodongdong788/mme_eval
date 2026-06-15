"""离线重判与单用例试判。"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from medeval import trace_store
from medeval.config import load_config
from medeval.models import CaseResult, RunReport
from medeval.reporter.aggregator import build_report
from medeval.run_slug import make_run_slug
from medeval.service import build_adjudicator, build_judges

from ..benchmarks import _apply_case_overrides
from ..db import session_scope
from ..models_db import Benchmark
from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .config_overrides import apply_adapter_overrides, apply_judge_overrides
from .eval_artifacts import apply_retention
from .eval_release_thresholds import (
    apply_release_threshold_overrides,
    load_release_threshold_overrides,
)
from .eval_source import frozen_cases_and_traces, load_source_run

logger = logging.getLogger(__name__)


def build_rejudge_job(
    run_id: int,
    *,
    source_run_id: int,
    run_name: str | None = None,
    judge_override: dict[str, Any] | None = None,
    cases_benchmark_id: int | None = None,
    only_release_failed: bool = False,
    settings: Settings | None = None,
) -> Callable[[InMemoryProgress], Awaitable[None]]:
    settings = settings or get_settings()

    async def job(progress: InMemoryProgress) -> None:
        from .. import eval_job as ej

        src_slug, _bm_id, judge_ov, adapter_ov = load_source_run(settings, source_run_id)
        src_dir = settings.outputs_dir / src_slug
        cases, per_case_traces, n_runs = frozen_cases_and_traces(
            src_dir, require_traces=True
        )

        if cases_benchmark_id is not None:
            with session_scope() as session:
                bm = session.get(Benchmark, cases_benchmark_id)
                if bm is None:
                    raise ValueError(f"判据 benchmark {cases_benchmark_id} 不存在")
                override_cases = ej.load_benchmark_cases(bm, settings=settings)
            ov_by_id = {c.sample_id: c for c in override_cases}
            cases = [ov_by_id.get(c.sample_id, c) for c in cases]

        config = load_config(settings.config_path)
        if run_name:
            config.run.name = run_name
        config.run.repeat = n_runs
        apply_judge_overrides(config, judge_ov)
        apply_adapter_overrides(config, adapter_ov)
        apply_judge_overrides(config, judge_override)
        with session_scope() as session:
            apply_release_threshold_overrides(
                config, load_release_threshold_overrides(session)
            )

        judges = build_judges(config.judges)
        adjudicator = build_adjudicator(config.judges)

        new_slug = make_run_slug(config.run.name)
        out_dir = settings.outputs_dir / new_slug

        src_bundle = trace_store.read_traces(src_dir)
        src_fp = src_bundle.meta.get("adapter_fingerprint", "") if src_bundle else ""

        if only_release_failed:
            src_report = RunReport.model_validate_json(
                (src_dir / "report.json").read_text(encoding="utf-8")
            )
            failed_ids = {
                r.case.sample_id for r in src_report.results if not r.release_passed
            }
            if not failed_ids:
                raise ValueError("源 run 无上线失败用例，无法只重判失败")
            sub_cases = []
            sub_traces = []
            for c, t in zip(cases, per_case_traces):
                if c.sample_id in failed_ids:
                    sub_cases.append(c)
                    sub_traces.append(t)
            partial = await ej.judge_traces(
                config,
                sub_cases,
                sub_traces,
                judges,
                adjudicator,
                progress=progress,
                run_name=new_slug,
                declare_plan=True,
            )
            new_by_id = {r.case.sample_id: r for r in partial.results}
            merged = [
                new_by_id.get(r.case.sample_id, r)
                if r.case.sample_id in failed_ids
                else r
                for r in src_report.results
            ]
            report = build_report(
                run_name=new_slug,
                results=merged,
                adapter_type=config.adapter.type,
                config_snapshot=config.model_dump(mode="json"),
                description=config.run.description,
                n_runs=n_runs,
            )
        else:
            report = await ej.judge_traces(
                config,
                cases,
                per_case_traces,
                judges,
                adjudicator,
                progress=progress,
                run_name=new_slug,
                declare_plan=True,
            )

        try:
            trace_store.write_traces(
                out_dir,
                cases,
                per_case_traces,
                store_raw=config.run.store_raw,
                meta={
                    "schema": trace_store.SCHEMA_VERSION,
                    "adapter_fingerprint": src_fp,
                    "store_raw": config.run.store_raw,
                    "n_runs": n_runs,
                    "n_cases": len(cases),
                    "rejudged_from": src_slug,
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "run %s 写 traces 失败（不影响落库）",
                run_id,
                exc_info=True,
            )

        ej._persist_outcome(
            run_id,
            report,
            out_dir,
            prev_json=src_dir / "report.json",
            parent_run_id=source_run_id,
        )
        apply_retention(config, settings)

    return job


async def preview_rejudge_case(
    *,
    source_run_id: int,
    sample_id: str,
    case_override: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> CaseResult:
    from .. import eval_job as ej

    settings = settings or get_settings()
    src_slug, _bm_id, judge_ov, adapter_ov = load_source_run(settings, source_run_id)
    src_dir = settings.outputs_dir / src_slug
    cases, per_case_traces, n_runs = frozen_cases_and_traces(src_dir, require_traces=True)

    idx = next((i for i, c in enumerate(cases) if c.sample_id == sample_id), None)
    if idx is None:
        raise ValueError(f"用例 {sample_id} 不在源 run 的结果中")
    sub_cases = [cases[idx]]
    sub_traces = [per_case_traces[idx]]

    if case_override:
        ov = dict(case_override)
        ov["sample_id"] = sample_id
        sub_cases = _apply_case_overrides(sub_cases, [ov])

    config = load_config(settings.config_path)
    config.run.repeat = n_runs
    apply_judge_overrides(config, judge_ov)
    apply_adapter_overrides(config, adapter_ov)
    with session_scope() as session:
        apply_release_threshold_overrides(
            config, load_release_threshold_overrides(session)
        )

    judges = build_judges(config.judges)
    adjudicator = build_adjudicator(config.judges)
    report = await ej.judge_traces(
        config,
        sub_cases,
        sub_traces,
        judges,
        adjudicator,
        declare_plan=False,
    )
    return report.results[0]
