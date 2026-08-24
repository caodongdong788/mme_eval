"""断点续跑 Job 构造与发起。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from medeval import trace_store
from medeval.run_slug import make_run_slug
from medeval.service import resolve_diff_target

from ..db import session_scope
from ..models_db import CaseResultRow, EvalRun
from ..job_specs import attach_job_spec
from ..jobs import commit_and_submit_job
from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .eval_artifacts import (
    IncrementalRunPersister,
    apply_retention,
    copy_case_image_snapshot,
    load_persisted_case_results,
    write_run_plan,
)
from .eval_stack import build_eval_adapter, build_judge_stack, prepare_run_config
from .eval_source import load_source_run, resume_cases_and_traces
from .runs import get_run_or_404, source_out_dir

if TYPE_CHECKING:
    from ..jobs import JobRunner


logger = logging.getLogger(__name__)


def _reset_incompatible_checkpoint(run_id: int, out_dir) -> None:
    """丢弃不能安全复用的中断留痕，以下次尝试的当前配置完整重跑。

    自动恢复绝不能把不同 adapter 配置生成的对话、判分或聚合混在同一个 Run 中。
    保留 Run 本身与审计信息，仅清除可重新生成的中间产物和阶段性结果。
    """
    for name in (trace_store.PARTIAL, trace_store.TRACES_GZ, "report.json", "transcripts.xlsx"):
        (out_dir / name).unlink(missing_ok=True)

    with session_scope() as session:
        session.execute(
            delete(CaseResultRow).where(CaseResultRow.run_id == run_id)
        )
        row = session.get(EvalRun, run_id)
        if row is None:
            return
        row.has_traces = False
        row.total = 0
        row.passed = 0
        row.pass_rate = 0.0
        row.medical_safety_failed = 0
        row.grading = {}
        row.stability_distribution = {}
        row.latency_summary = {}
        row.ttft_summary = {}
        row.token_summary = {}
        row.pass_rate_ci = {}
        row.guideline_match = {}
        row.failure_tag_counter = {}
        row.judge_fingerprints = {}
        row.by_level = {}
        row.by_scenario = {}
        row.by_case_type = {}


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
    """在原评测记录上恢复中断任务，不新建一条续跑记录。"""
    source = get_run_or_404(session, source_run_id)
    validate_resume_preconditions(source)
    # 仅重置任务态；已增量落库的 Case 明细、原始创建人和运行名称均应保留。
    source.status = "pending"
    source.error_msg = ""
    source.finished_at = None
    source.progress = {}
    job = build_resume_job(
        source.id,
        source_run_id=source.id,
        run_name=source.name,
        in_place=True,
    )
    await commit_and_submit_job(
        session,
        source.id,
        job,
        job_runner=job_runner,
        failure_message="续跑任务提交执行队列失败",
    )
    return source


def build_resume_job(
    run_id: int,
    *,
    source_run_id: int,
    run_name: str | None = None,
    in_place: bool = False,
    restart_on_fingerprint_mismatch: bool = False,
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
        judges = build_judge_stack(config)

        new_slug = src_slug if in_place else make_run_slug(config.run.name)
        out_dir = src_dir if in_place else settings.outputs_dir / new_slug
        write_run_plan(out_dir, cases, n_runs)
        if out_dir != src_dir:
            copy_case_image_snapshot(src_dir, out_dir)
        sample_ids = [case.sample_id for case in cases]
        resume_dir = src_dir
        completed_results = load_persisted_case_results(run_id, sample_ids) if in_place else {}

        if restart_on_fingerprint_mismatch:
            bundle = trace_store.read_traces(src_dir)
            saved_fingerprint = (bundle.meta.get("adapter_fingerprint") if bundle else "") or ""
            current_fingerprint = trace_store.adapter_fingerprint(
                config.adapter.type,
                config.adapter.model_dump(),
            )
            if saved_fingerprint and saved_fingerprint != current_fingerprint:
                logger.warning(
                    "run %s 自动恢复时 adapter 指纹不一致（当前 %s，留痕 %s），"
                    "将清理中断留痕并按当前配置完整重跑",
                    run_id,
                    current_fingerprint,
                    saved_fingerprint,
                )
                _reset_incompatible_checkpoint(run_id, out_dir)
                resume_dir = None
                completed_results = {}
        progress.set_case_complete_callback(
            IncrementalRunPersister(
                run_id,
                run_name=new_slug,
                adapter_type=config.adapter.type,
                config_snapshot=config.public_snapshot(),
                description=config.run.description,
                n_runs=n_runs,
                sample_order=sample_ids,
                initial_results=completed_results.values(),
            )
        )

        report = await ej.evaluate(
            config,
            cases,
            adapter,
            judges,
            progress=progress,
            run_name=new_slug,
            account_owner=str(run_id),
            out_dir=out_dir,
            resume_dir=resume_dir,
            completed_results=completed_results,
        )

        prev = resolve_diff_target("auto", settings.outputs_dir, out_dir)
        ej._persist_outcome(
            run_id,
            report,
            out_dir,
            prev_json=prev,
            parent_run_id=None if in_place else source_run_id,
        )
        apply_retention(config, settings)

    return attach_job_spec(
        job,
        "resume",
        {
            "source_run_id": source_run_id,
            "run_name": run_name,
            "in_place": in_place,
        },
    )
