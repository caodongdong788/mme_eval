"""正常评测 Job 构造。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import hashlib
import json
from pathlib import Path
from typing import Any

from medeval.run_slug import make_run_slug
from medeval.service import resolve_diff_target
from medeval.assertions import refresh_result_assertions
from medeval.reporter.aggregator import refresh_report

from ..db import session_scope
from ..job_specs import attach_job_spec, without_api_keys
from ..models_db import Benchmark, EvalRun
from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .eval_artifacts import (
    IncrementalRunPersister,
    apply_retention,
    snapshot_case_images,
    write_run_plan,
)
from .eval_stack import build_eval_adapter, build_judge_stack, prepare_run_config
from .langfuse_trace import enrich_report_agent_chains, schedule_run_agent_chain_backfill


def build_eval_job(
    run_id: int,
    *,
    benchmark_id: int,
    run_name: str | None = None,
    levels: list[str] | None = None,
    limit: int = 0,
    repeat: int | None = None,
    judge_full: dict[str, Any] | None = None,
    adapter_full: dict[str, Any] | None = None,
    judge_model_id: int | None = None,
    user_simulator_model_id: int | None = None,
    settings: Settings | None = None,
) -> Callable[[InMemoryProgress], Awaitable[None]]:
    settings = settings or get_settings()
    levels = levels or []

    async def job(progress: InMemoryProgress) -> None:
        from .. import eval_job as ej

        config = prepare_run_config(
            settings,
            run_name=run_name,
            repeat=repeat,
            judge_ov=judge_full,
            adapter_ov=adapter_full,
        )

        with session_scope() as session:
            bm = session.get(Benchmark, benchmark_id)
            if bm is None:
                raise ValueError(f"benchmark {benchmark_id} 不存在")
            cases = ej.load_benchmark_cases(bm, settings=settings)
            benchmark_root = Path(bm.storage_path)
            benchmark_meta = {
                "id": bm.id,
                "name": bm.name,
                "suite_type": bm.suite_type,
            }
        if levels:
            level_set = set(levels)
            cases = [c for c in cases if getattr(c.level, "value", c.level) in level_set]
        if limit:
            cases = cases[:limit]
        benchmark_meta.update({
            "case_count": len(cases),
            "sample_ids": [case.sample_id for case in cases],
            "fingerprint": hashlib.sha256(
                json.dumps(
                    [case.model_dump(mode="json", by_alias=True) for case in cases],
                    ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        })

        adapter = build_eval_adapter(config)
        judges = build_judge_stack(config)

        # 首次启动就固定 slug 并落库。Worker 若在第一条 Case 完成前退出，下一实例仍能
        # 定位同一个 partial trace 目录，而不会另建目录丢失断点。
        with session_scope() as session:
            run_row = session.get(EvalRun, run_id)
            existing_slug = run_row.run_slug if run_row is not None else ""
        run_slug = (
            existing_slug
            if existing_slug and existing_slug != "(pending)"
            else make_run_slug(config.run.name)
        )
        out_dir = settings.outputs_dir / run_slug
        write_run_plan(out_dir, cases, config.run.repeat or 1)
        if not benchmark_root.is_absolute():
            benchmark_root = settings.project_root / benchmark_root
        snapshot_case_images(out_dir, cases, benchmark_root)

        partial_config = config.public_snapshot()
        partial_config["benchmark"] = benchmark_meta
        with session_scope() as session:
            run_row = session.get(EvalRun, run_id)
            if run_row is None:
                raise ValueError(f"run {run_id} 不存在")
            run_row.run_slug = run_slug
            run_row.adapter_type = config.adapter.type
            run_row.config_snapshot = partial_config
            run_row.description = config.run.description
            run_row.n_runs = config.run.repeat or 1
        progress.set_case_complete_callback(
            IncrementalRunPersister(
                run_id,
                run_name=run_slug,
                adapter_type=config.adapter.type,
                config_snapshot=partial_config,
                description=config.run.description,
                n_runs=config.run.repeat or 1,
                sample_order=[case.sample_id for case in cases],
            )
        )

        report = await ej.evaluate(
            config,
            cases,
            adapter,
            judges,
            progress=progress,
            run_name=run_slug,
            account_owner=str(run_id),
            out_dir=out_dir,
        )
        await enrich_report_agent_chains(report, settings)
        # 工具/RAG 断言以同步后的真实 Agent 链路为准；随后重算 release gate 和聚合。
        for result in report.results:
            refresh_result_assertions(result)
        refresh_report(report)
        report.config_snapshot["benchmark"] = benchmark_meta

        prev = resolve_diff_target("auto", settings.outputs_dir, out_dir)
        ej._persist_outcome(run_id, report, out_dir, prev_json=prev)
        # Langfuse 可能在评测请求结束后才异步落盘；首轮同步读空的 Case 由后台
        # 延迟补拉并回填 RAG 列，不阻塞任务成功状态或占用评测账号。
        schedule_run_agent_chain_backfill(run_id, settings)
        apply_retention(config, settings)

    return attach_job_spec(
        job,
        "evaluation",
        without_api_keys(
            {
                "benchmark_id": benchmark_id,
                "run_name": run_name,
                "levels": levels,
                "limit": limit,
                "repeat": repeat,
                "judge": judge_full,
                "adapter": adapter_full,
                "judge_model_id": judge_model_id,
                "user_simulator_model_id": user_simulator_model_id,
            }
        ),
    )
