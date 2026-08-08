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
from ..models_db import Benchmark
from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .eval_artifacts import (
    IncrementalRunPersister,
    apply_retention,
    snapshot_case_images,
    write_run_plan,
)
from .eval_stack import build_eval_adapter, build_judge_stack, prepare_run_config
from .langfuse_trace import enrich_report_agent_chains


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

        run_slug = make_run_slug(config.run.name)
        out_dir = settings.outputs_dir / run_slug
        write_run_plan(out_dir, cases, config.run.repeat or 1)
        if not benchmark_root.is_absolute():
            benchmark_root = settings.project_root / benchmark_root
        snapshot_case_images(out_dir, cases, benchmark_root)

        partial_config = config.public_snapshot()
        partial_config["benchmark"] = benchmark_meta
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
        apply_retention(config, settings)

    return job
