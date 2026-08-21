"""离线重判与单用例试判。"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from medeval import trace_store
from medeval.models import CaseResult, RunReport
from medeval.reporter.aggregator import build_report
from medeval.run_slug import make_run_slug
from medeval.visible_response import normalize_cx_agent_visible_trace

from ..benchmarks import _apply_case_overrides
from ..db import session_scope
from ..models_db import Benchmark
from ..job_specs import attach_job_spec, without_api_keys
from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .eval_artifacts import (
    IncrementalRunPersister,
    apply_retention,
    copy_case_image_snapshot,
)
from .eval_stack import build_judge_stack, prepare_run_config
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
    judge_model_id: int | None = None,
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

        config = prepare_run_config(
            settings,
            run_name=run_name,
            repeat=n_runs,
            judge_ov=judge_ov,
            adapter_ov=adapter_ov,
            extra_judge_ov=judge_override,
        )

        # 历史 CX run 的 trace 保存的是原始 SSE 文本，其中可能含用户页面已隐藏的
        # 标题分类标签。离线重判也必须与当前在线评测采用相同的可见文本口径。
        if config.adapter.type == "cx_agent":
            per_case_traces = [
                [normalize_cx_agent_visible_trace(trace) for trace in traces]
                for traces in per_case_traces
            ]

        judges = build_judge_stack(config)

        new_slug = make_run_slug(config.run.name)
        out_dir = settings.outputs_dir / new_slug
        copy_case_image_snapshot(src_dir, out_dir)

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
            progress.set_case_complete_callback(
                IncrementalRunPersister(
                    run_id,
                    run_name=new_slug,
                    adapter_type=config.adapter.type,
                    config_snapshot=config.public_snapshot(),
                    description=config.run.description,
                    n_runs=n_runs,
                    sample_order=[case.sample_id for case in sub_cases],
                )
            )
            partial = await ej.judge_traces(
                config,
                sub_cases,
                sub_traces,
                judges,
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
                config_snapshot=config.public_snapshot(),
                description=config.run.description,
                n_runs=n_runs,
            )
        else:
            progress.set_case_complete_callback(
                IncrementalRunPersister(
                    run_id,
                    run_name=new_slug,
                    adapter_type=config.adapter.type,
                    config_snapshot=config.public_snapshot(),
                    description=config.run.description,
                    n_runs=n_runs,
                    sample_order=[case.sample_id for case in cases],
                )
            )
            report = await ej.judge_traces(
                config,
                cases,
                per_case_traces,
                judges,
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

    return attach_job_spec(
        job,
        "rejudge",
        without_api_keys(
            {
                "source_run_id": source_run_id,
                "run_name": run_name,
                "judge_override": judge_override,
                "judge_model_id": judge_model_id,
                "cases_benchmark_id": cases_benchmark_id,
                "only_release_failed": only_release_failed,
            }
        ),
    )


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

    config = prepare_run_config(
        settings,
        repeat=n_runs,
        judge_ov=judge_ov,
        adapter_ov=adapter_ov,
    )

    judges = build_judge_stack(config)
    report = await ej.judge_traces(
        config,
        sub_cases,
        sub_traces,
        judges,
        declare_plan=False,
    )
    return report.results[0]
