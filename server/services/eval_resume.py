"""断点续跑 Job 构造与发起。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy.orm import Session

from medeval import trace_store
from medeval.run_slug import make_run_slug
from medeval.service import resolve_diff_target

from ..models_db import EvalRun
from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .eval_artifacts import apply_retention, write_run_plan
from .eval_stack import build_eval_adapter, build_judge_stack, prepare_run_config
from .eval_source import load_source_run, resume_cases_and_traces
from .runs import create_derived_run, get_run_or_404, source_out_dir

if TYPE_CHECKING:
    from ..jobs import JobRunner


def validate_resume_preconditions(source: EvalRun) -> None:
    """续跑闸门：源 run 状态与可复用留痕。"""
    if source.status in ("running", "pending"):
        raise HTTPException(status_code=400, detail="运行中或等待中的评测不可续跑")
    out_dir = source_out_dir(source)
    if out_dir is None:
        raise HTTPException(status_code=400, detail="源 run 产物目录缺失，无法续跑")
    has_report = (out_dir / "report.json").is_file()
    has_traces = (out_dir / trace_store.TRACES_GZ).is_file() or (
        out_dir / trace_store.PARTIAL
    ).is_file()
    if not has_traces and not has_report:
        raise HTTPException(
            status_code=400,
            detail="源 run 无可复用留痕（从未落盘或已被存储治理清理），无法续跑",
        )
    if not has_report and source.benchmark_id is None:
        raise HTTPException(
            status_code=400, detail="源 run 未关联 benchmark，无法重建用例集续跑"
        )


async def launch_resume_run(
    session: Session,
    source_run_id: int,
    *,
    job_runner: "JobRunner",
    build_resume_job,
) -> EvalRun:
    """校验源 run → 派生 pending run → 提交续跑 job。"""
    source = get_run_or_404(session, source_run_id)
    validate_resume_preconditions(source)
    derived = create_derived_run(session, source, suffix="续跑")
    job = build_resume_job(derived.id, source_run_id=source.id, run_name=derived.name)
    await job_runner.submit(derived.id, job)
    return derived


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

        config = prepare_run_config(
            settings,
            run_name=run_name,
            repeat=n_runs,
            judge_ov=judge_ov,
            adapter_ov=adapter_ov,
        )

        adapter = build_eval_adapter(config)
        judges, adjudicator = build_judge_stack(config)

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
