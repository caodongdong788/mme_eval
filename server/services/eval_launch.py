"""正常评测 Job 构造。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from medeval.run_slug import make_run_slug
from medeval.service import resolve_diff_target

from ..db import session_scope
from ..models_db import Benchmark
from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .eval_artifacts import apply_retention, write_run_plan
from .eval_stack import build_eval_adapter, build_judge_stack, prepare_run_config


def build_eval_job(
    run_id: int,
    *,
    benchmark_id: int,
    run_name: str | None = None,
    score_profiles: list[str] | None = None,
    levels: list[str] | None = None,
    limit: int = 0,
    repeat: int | None = None,
    judge_full: dict[str, Any] | None = None,
    adapter_full: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> Callable[[InMemoryProgress], Awaitable[None]]:
    settings = settings or get_settings()
    score_profiles = score_profiles or []
    levels = levels or []

    async def job(progress: InMemoryProgress) -> None:
        from .. import eval_job as ej

        config = prepare_run_config(
            settings,
            run_name=run_name,
            repeat=repeat,
            judge_ov=judge_full,
            adapter_ov=adapter_full,
            release_thresholds=True,
        )
        if score_profiles:
            config.cases.score_profiles = list(score_profiles)

        with session_scope() as session:
            bm = session.get(Benchmark, benchmark_id)
            if bm is None:
                raise ValueError(f"benchmark {benchmark_id} 不存在")
            cases = ej.load_benchmark_cases(
                bm, score_profiles=score_profiles or None, settings=settings
            )
        if levels:
            level_set = set(levels)
            cases = [c for c in cases if getattr(c.level, "value", c.level) in level_set]
        if limit:
            cases = cases[:limit]

        adapter = build_eval_adapter(config)
        judges, adjudicator = build_judge_stack(config)

        run_slug = make_run_slug(config.run.name)
        out_dir = settings.outputs_dir / run_slug
        write_run_plan(out_dir, cases, config.run.repeat or 1)

        report = await ej.evaluate(
            config,
            cases,
            adapter,
            judges,
            adjudicator,
            progress=progress,
            run_name=run_slug,
            out_dir=out_dir,
        )

        prev = resolve_diff_target("auto", settings.outputs_dir, out_dir)
        ej._persist_outcome(run_id, report, out_dir, prev_json=prev)
        apply_retention(config, settings)

    return job
