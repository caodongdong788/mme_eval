"""断点续跑 Job 构造。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from medeval.config import load_config
from medeval.run_slug import make_run_slug
from medeval.service import (
    build_adjudicator,
    build_judges,
    resolve_diff_target,
)

from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .config_overrides import apply_adapter_overrides, apply_judge_overrides
from .eval_artifacts import apply_retention, write_run_plan
from .eval_source import load_source_run, resume_cases_and_traces


def build_resume_job(
    run_id: int,
    *,
    source_run_id: int,
    run_name: str | None = None,
    settings: Settings | None = None,
) -> Callable[[InMemoryProgress], Awaitable[None]]:
    settings = settings or get_settings()

    async def job(progress: InMemoryProgress) -> None:
        from .. import eval_job as ej

        src_slug, bm_id, judge_ov, adapter_ov = load_source_run(settings, source_run_id)
        src_dir = settings.outputs_dir / src_slug
        cases, _per_case_traces, n_runs = resume_cases_and_traces(
            src_dir, settings, bm_id
        )

        config = load_config(settings.config_path)
        if run_name:
            config.run.name = run_name
        config.run.repeat = n_runs
        apply_judge_overrides(config, judge_ov)
        apply_adapter_overrides(config, adapter_ov)

        adapter = ej.build_adapter(config.adapter.type, config.adapter.model_dump())
        judges = build_judges(config.judges)
        adjudicator = build_adjudicator(config.judges)

        new_slug = make_run_slug(config.run.name)
        out_dir = settings.outputs_dir / new_slug
        write_run_plan(out_dir, cases, n_runs)

        report = await ej.evaluate(
            config,
            cases,
            adapter,
            judges,
            adjudicator,
            progress=progress,
            run_name=new_slug,
            out_dir=out_dir,
            resume_dir=src_dir,
        )

        prev = resolve_diff_target("auto", settings.outputs_dir, out_dir)
        ej._persist_outcome(
            run_id, report, out_dir, prev_json=prev, parent_run_id=source_run_id
        )
        apply_retention(config, settings)

    return job
