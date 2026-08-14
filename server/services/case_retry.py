"""在原评测中重新执行单个 Case，并用新结果替换旧结果。"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.models import CaseResult
from medeval.reporter.aggregator import build_report
from medeval.service import write_core_artifacts

from ..db import session_scope
from ..ingest import build_case_row, populate_run_summary, update_case_row
from ..models_db import Benchmark, CaseResultRow, EvalRun
from ..job_specs import attach_job_spec
from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .eval_launch import enrich_report_agent_chains
from medeval.assertions import refresh_result_assertions
from medeval.reporter.aggregator import refresh_report
from .eval_source import frozen_cases_and_traces, load_source_run
from .eval_stack import build_eval_adapter, build_judge_stack, prepare_run_config
from .runs import get_run_or_404, source_out_dir

if TYPE_CHECKING:
    from ..jobs import JobRunner


logger = logging.getLogger(__name__)


class CaseRetryError(Exception):
    """单用例重试的可展示业务错误。"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _replace_case_row(target: CaseResultRow, result: CaseResult, pricing: dict | None) -> None:
    replacement = build_case_row(target.run_id, result, pricing)
    update_case_row(target, replacement)


def validate_case_retry(
    session: Session, run_id: int, sample_ids: list[str]
) -> EvalRun:
    """校验当前 run 可以重试，且源 Case 和冻结用例仍在。"""
    source = get_run_or_404(session, run_id)
    if source.status in {"pending", "running"}:
        raise CaseRetryError(409, "该评测正在执行，暂不能重试单个 Case")
    if source.status not in {"success", "failed"}:
        raise CaseRetryError(400, "当前评测状态不支持单用例重试")
    if source_out_dir(source) is None or not (source_out_dir(source) / "report.json").is_file():
        raise CaseRetryError(400, "当前 run 缺 report.json（产物已清理），无法重试")
    existing_ids = set(session.scalars(
        select(CaseResultRow.sample_id).where(
            CaseResultRow.run_id == run_id,
            CaseResultRow.sample_id.in_(sample_ids),
        )
    ))
    missing = next((sample_id for sample_id in sample_ids if sample_id not in existing_ids), None)
    if missing is not None:
        raise CaseRetryError(404, f"用例 {missing} 不在当前评测中")
    return source


async def launch_case_retry(
    session: Session,
    run_id: int,
    sample_id: str,
    *,
    job_runner: "JobRunner",
    build_retry_case_job,
) -> EvalRun:
    """把当前 run 置为 pending 并提交该 Case 的真实调用任务。"""
    source = validate_case_retry(session, run_id, [sample_id])
    source.status = "pending"
    source.error_msg = ""
    source.progress = {"context": {"kind": "case_retry", "sample_id": sample_id}}
    session.commit()
    job = build_retry_case_job(run_id, sample_id=sample_id)
    await job_runner.submit(run_id, job)
    return source


async def launch_cases_retry(
    session: Session,
    run_id: int,
    *,
    sample_ids: list[str],
    job_runner: "JobRunner",
    build_retry_cases_job,
) -> EvalRun:
    """在原评测记录中批量重新执行选中的 Case，并逐条覆盖旧结果。"""
    ordered_ids = list(dict.fromkeys(sample_id.strip() for sample_id in sample_ids if sample_id.strip()))
    source = validate_case_retry(session, run_id, ordered_ids)
    source.status = "pending"
    source.error_msg = ""
    source.progress = {
        "context": {
            "kind": "cases_retry",
            "sample_ids": ordered_ids,
        }
    }
    # 先提交事务，避免后台 job 的 running 状态被当前请求的 pending 覆盖。
    session.commit()
    job = build_retry_cases_job(run_id, sample_ids=ordered_ids)
    await job_runner.submit(run_id, job)
    return source


def build_retry_case_job(
    run_id: int,
    *,
    sample_id: str,
    settings: Settings | None = None,
) -> Callable[[InMemoryProgress], Awaitable[None]]:
    """构建单 Case 的完整评测任务：真实调用 adapter，再重跑全部判分。"""
    return build_retry_cases_job(run_id, sample_ids=[sample_id], settings=settings)


def build_retry_cases_job(
    run_id: int,
    *,
    sample_ids: list[str],
    settings: Settings | None = None,
) -> Callable[[InMemoryProgress], Awaitable[None]]:
    """构建批量完整评测任务：真实调用 Agent 后逐条覆盖所选结果。"""
    settings = settings or get_settings()
    ordered_ids = list(dict.fromkeys(sample_id.strip() for sample_id in sample_ids if sample_id.strip()))

    async def job(progress: InMemoryProgress) -> None:
        from .. import eval_job as ej

        src_slug, benchmark_id, judge_ov, adapter_ov = load_source_run(settings, run_id)
        src_dir = settings.outputs_dir / src_slug
        cases, _old_traces, n_runs = frozen_cases_and_traces(src_dir, require_traces=False)
        selected = [item for item in cases if item.sample_id in set(ordered_ids)]
        found_ids = {item.sample_id for item in selected}
        missing = next((sample_id for sample_id in ordered_ids if sample_id not in found_ids), None)
        if missing is not None:
            raise ValueError(f"用例 {missing} 不在当前 run 的冻结报告中")
        # report.json 只保留相对图片路径、不持久化图片 base64；单 Case 重试时从关联
        # benchmark 重新加载该题，以恢复 ZIP images/ 中的运行时图片内容。
        if benchmark_id is not None:
            with session_scope() as source_session:
                benchmark = source_session.get(Benchmark, benchmark_id)
                if benchmark is not None and Path(benchmark.storage_path).exists():
                    current_cases = ej.load_benchmark_cases(benchmark, settings=settings)
                    current_by_id = {item.sample_id: item for item in current_cases}
                    selected = [current_by_id.get(item.sample_id, item) for item in selected]

        config = prepare_run_config(
            settings,
            run_name=src_slug,
            repeat=n_runs,
            judge_ov=judge_ov,
            adapter_ov=adapter_ov,
        )
        adapter = build_eval_adapter(config)
        judges = build_judge_stack(config)
        retried = await ej.evaluate(
            config,
            selected,
            adapter,
            judges,
            progress=progress,
            run_name=src_slug,
            account_owner=str(run_id),
        )
        await enrich_report_agent_chains(retried, settings)
        for result in retried.results:
            refresh_result_assertions(result)
        refresh_report(retried)
        with session_scope() as db_session:
            run = db_session.get(EvalRun, run_id)
            if run is None:
                raise ValueError(f"run {run_id} 不存在")
            rows = db_session.execute(
                select(CaseResultRow)
                .where(CaseResultRow.run_id == run_id)
                .order_by(CaseResultRow.id)
            ).scalars().all()
            retried_by_id = {result.case.sample_id: result for result in retried.results}

            merged_results = [
                retried_by_id[row.sample_id]
                if row.sample_id in retried_by_id
                else CaseResult.model_validate(row.detail_json)
                for row in rows
            ]
            merged = build_report(
                run_name=run.run_slug,
                results=merged_results,
                adapter_type=run.adapter_type or config.adapter.type,
                config_snapshot=run.config_snapshot or config.public_snapshot(),
                description=run.description,
                started_at=run.started_at,
                n_runs=run.n_runs or n_runs,
            )
            for target in rows:
                replacement = retried_by_id.get(target.sample_id)
                if replacement is not None:
                    _replace_case_row(
                        target,
                        replacement,
                        (merged.config_snapshot or {}).get("cost"),
                    )
            populate_run_summary(run, merged)
            run.status = "success"
            run.error_msg = ""

        try:
            # 同步更新 report.json/transcripts，避免之后重判或导出又读到重试前的结果。
            write_core_artifacts(merged, src_dir, prev_json=None)
        except Exception:  # noqa: BLE001 - 磁盘产物失败不应吞掉新的数据库结果
            logger.warning("run %s 批量用例重试后写产物失败", run_id, exc_info=True)

    return attach_job_spec(
        job,
        "cases_retry",
        {"sample_ids": ordered_ids},
    )
