"""正常评测 Job 构造。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from medeval.config import load_config
from medeval.run_slug import make_run_slug
from medeval.service import (
    build_adjudicator,
    build_judges,
    resolve_diff_target,
)

from ..db import session_scope
from ..models_db import Benchmark
from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .config_overrides import apply_adapter_overrides, apply_judge_overrides
from .eval_artifacts import apply_retention, write_run_plan
from .eval_release_thresholds import (
    apply_release_threshold_overrides,
    load_release_threshold_overrides,
)


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

        config = load_config(settings.config_path)
        if run_name:
            config.run.name = run_name
        if score_profiles:
            config.cases.score_profiles = list(score_profiles)
        if repeat:
            config.run.repeat = repeat
        apply_judge_overrides(config, judge_full)
        apply_adapter_overrides(config, adapter_full)

        with session_scope() as session:
            bm = session.get(Benchmark, benchmark_id)
            if bm is None:
                raise ValueError(f"benchmark {benchmark_id} 不存在")
            cases = ej.load_benchmark_cases(
                bm, score_profiles=score_profiles or None, settings=settings
            )
            apply_release_threshold_overrides(
                config, load_release_threshold_overrides(session)
            )
        if levels:
            level_set = set(levels)
            cases = [c for c in cases if getattr(c.level, "value", c.level) in level_set]
        if limit:
            cases = cases[:limit]

        adapter = ej.build_adapter(config.adapter.type, config.adapter.model_dump())
        judges = build_judges(config.judges)
        adjudicator = build_adjudicator(config.judges)

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
