"""在原评测中重新执行单个 Case，并用新结果替换旧结果。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.models import CaseResult
from medeval.reporter.aggregator import build_report
from medeval.service import write_core_artifacts

from ..benchmarks import load_benchmark_cases
from ..db import session_scope
from ..ingest import build_case_row, populate_run_summary, update_case_row
from ..models_db import Benchmark, CaseResultRow, EvalRun
from ..job_specs import attach_job_spec
from ..jobs import enqueue_database_job_in_session
from ..progress import InMemoryProgress
from ..settings import Settings, get_settings
from .eval_launch import enrich_report_agent_chains
from medeval.assertions import refresh_result_assertions
from medeval.reporter.scoring import apply_grading
from medeval.reporter.aggregator import refresh_report
from .eval_source import load_source_run
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


class IncrementalRetryPersister:
    """批量重新评测时，完成一个 Case 就原位替换并刷新聚合指标。

    ``evaluate`` 会在每条 Case 完成所有对话、八维评分和指南评分后触发回调。这里
    串行写库，避免多个并发 Case 同时重建 run 汇总时互相覆盖。最终任务仍会写完整
    report.json；若中断，已完成 Case 的数据库结果已可见且不会丢失。
    """

    def __init__(self, run_id: int) -> None:
        self.run_id = run_id
        self._lock = asyncio.Lock()

    async def __call__(self, result: CaseResult) -> None:
        async with self._lock:
            with session_scope() as session:
                run = session.get(EvalRun, self.run_id)
                if run is None:
                    raise ValueError(f"run {self.run_id} 不存在")
                target = session.execute(
                    select(CaseResultRow)
                    .where(
                        CaseResultRow.run_id == self.run_id,
                        CaseResultRow.sample_id == result.case.sample_id,
                    )
                    .order_by(CaseResultRow.id)
                ).scalars().first()
                if target is None:
                    raise ValueError(
                        f"run {self.run_id} 不存在 Case {result.case.sample_id}"
                    )

                pricing = (run.config_snapshot or {}).get("cost")
                report_snapshot = {**(run.config_snapshot or {}), "scoring_standard": run.scoring_standard}
                _replace_case_row(target, result, pricing)
                rows = session.execute(
                    select(CaseResultRow)
                    .where(CaseResultRow.run_id == self.run_id)
                    .order_by(CaseResultRow.id)
                ).scalars().all()
                merged = build_report(
                    run_name=run.run_slug,
                    results=[CaseResult.model_validate(row.detail_json) for row in rows],
                    adapter_type=run.adapter_type,
                    config_snapshot=report_snapshot,
                    description=run.description,
                    started_at=run.started_at,
                    n_runs=run.n_runs or 1,
                )
                # 运行中的重评不能因为刷新汇总而提前变为结束状态或出现结束时间。
                status, error_msg = run.status, run.error_msg
                started_at, finished_at = run.started_at, run.finished_at
                populate_run_summary(run, merged)
                run.status, run.error_msg = status, error_msg
                run.started_at, run.finished_at = started_at, finished_at


def _ensure_retry_queue_is_idle(job_runner: "JobRunner", run_id: int) -> None:
    """阻止重试覆盖同一 Run 尚未结束的持久化任务。

    数据库队列会在服务重启后续跑旧任务。若此时直接把 Run 改为“单条重评”，
    ``enqueue_job`` 为保持幂等会复用旧 job，最终形成“界面选 1 条、后台跑全量”
    的范围错配。必须先拒绝请求，等旧任务结束或取消后才能发起新的重评。
    """
    queue_snapshot = getattr(job_runner, "queue_snapshot", None)
    active = queue_snapshot(run_id) if callable(queue_snapshot) else None
    if active:
        state = "运行中" if active.get("state") == "running" else "排队中"
        raise CaseRetryError(409, f"该评测已有{state}任务，请等待完成或先终止后再重新评测")


def _retry_context(run: EvalRun) -> dict:
    progress = run.progress if isinstance(run.progress, dict) else {}
    context = progress.get("context")
    return dict(context) if isinstance(context, dict) else {}


def _cancelled_case_states(run: EvalRun) -> dict[str, dict]:
    """保留已完成 Case，其余被选 Case 标为已取消。"""
    progress = run.progress if isinstance(run.progress, dict) else {}
    context = _retry_context(run)
    selected_ids = list(context.get("sample_ids") or [])
    if context.get("kind") == "case_retry" and context.get("sample_id"):
        selected_ids = [context["sample_id"]]
    existing = progress.get("case_states") if isinstance(progress.get("case_states"), dict) else {}
    states: dict[str, dict] = {}
    for sample_id in selected_ids:
        previous = existing.get(sample_id) if isinstance(existing.get(sample_id), dict) else {}
        if previous.get("status") == "completed":
            states[sample_id] = {**previous, "status": "completed", "percent": 100}
        else:
            states[sample_id] = {**previous, "status": "cancelled"}
    return states


def _replace_case_row(target: CaseResultRow, result: CaseResult, pricing: dict | None) -> None:
    replacement = build_case_row(target.run_id, result, pricing)
    update_case_row(target, replacement)


def _retry_launch_snapshot(run: EvalRun) -> dict:
    """保存提交重试任务前的 Run 状态，入队失败时原样恢复。"""
    return {
        "status": run.status,
        "error_msg": run.error_msg,
        "progress": dict(run.progress or {}),
        "finished_at": run.finished_at,
    }


def _restore_failed_retry_launch(
    session: Session,
    run_id: int,
    snapshot: dict,
) -> None:
    """避免任务提交异常后遗留没有队列 Job 的 pending Run。"""
    session.expire_all()
    run = session.get(EvalRun, run_id)
    if run is None:
        return
    run.status = snapshot["status"]
    run.error_msg = snapshot["error_msg"]
    run.progress = snapshot["progress"]
    run.finished_at = snapshot["finished_at"]
    session.commit()


def validate_case_retry(
    session: Session, run_id: int, sample_ids: list[str]
) -> EvalRun:
    """校验当前 run 可以重试，且待重评 Case 属于该 Run。"""
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
    _ensure_retry_queue_is_idle(job_runner, run_id)
    source = validate_case_retry(session, run_id, [sample_id])
    previous = _retry_launch_snapshot(source)
    source.status = "pending"
    source.error_msg = ""
    source.progress = {"context": {"kind": "case_retry", "sample_id": sample_id}}
    job = build_retry_case_job(run_id, sample_id=sample_id)
    if enqueue_database_job_in_session(session, job_runner, run_id, job):
        session.commit()
        return source
    session.commit()
    try:
        await job_runner.submit(run_id, job)
    except BaseException:
        _restore_failed_retry_launch(session, run_id, previous)
        raise
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
    _ensure_retry_queue_is_idle(job_runner, run_id)
    source = validate_case_retry(session, run_id, ordered_ids)
    previous = _retry_launch_snapshot(source)
    source.status = "pending"
    source.error_msg = ""
    source.progress = {
        "context": {
            "kind": "cases_retry",
            "sample_ids": ordered_ids,
        }
    }
    job = build_retry_cases_job(run_id, sample_ids=ordered_ids)
    if enqueue_database_job_in_session(session, job_runner, run_id, job):
        session.commit()
        return source
    # 进程内任务必须先看到 pending 状态。
    session.commit()
    try:
        await job_runner.submit(run_id, job)
    except BaseException:
        _restore_failed_retry_launch(session, run_id, previous)
        raise
    return source


async def cancel_cases_retry(
    session: Session,
    run_id: int,
    *,
    job_runner: "JobRunner",
) -> EvalRun:
    """只终止当前批量重评，不删除原评测及其历史结果。"""
    source = get_run_or_404(session, run_id)
    context = _retry_context(source)
    if context.get("kind") not in {"case_retry", "cases_retry"}:
        raise CaseRetryError(409, "当前没有可终止的重新评测任务")
    if source.status not in {"pending", "running"}:
        raise CaseRetryError(409, "当前重新评测已经结束")
    if not await job_runner.cancel(run_id):
        raise CaseRetryError(409, "重新评测任务已结束，请刷新页面后查看结果")

    # DatabaseJobRunner.cancel 会等待 Worker 停止写入；此时将运行记录恢复为成功，
    # 因为未重评的 Case 仍保留原有有效结果。进度中明确标记被取消的 Case。
    session.expire_all()
    source = get_run_or_404(session, run_id)
    context = _retry_context(source)
    states = _cancelled_case_states(source)
    completed = sum(1 for value in states.values() if value.get("status") == "completed")
    source.status = "success"
    source.error_msg = ""
    source.progress = {
        **(source.progress if isinstance(source.progress, dict) else {}),
        "context": context,
        "case_states": states,
        "case_total": len(states),
        "case_done": completed,
        "cancelled": True,
        "completed": False,
    }
    session.commit()
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
        if benchmark_id is None:
            raise ValueError(f"run {run_id} 未关联 benchmark，无法读取最新用例")
        # “重新评测”面向 Benchmark 当前版本：重新读取包括问题、上下文、检查点和
        # 好答案在内的完整 Case。完成后由 IncrementalRetryPersister 原位覆盖该 Case
        # 的旧结果；历史 run 中未被选中的 Case 保持不变。
        with session_scope() as source_session:
            source_run = source_session.get(EvalRun, run_id)
            benchmark = source_session.get(Benchmark, benchmark_id)
            if source_run is None:
                raise ValueError(f"run {run_id} 不存在")
            if benchmark is None:
                raise ValueError(f"run {run_id} 关联的 benchmark {benchmark_id} 不存在")
            current_by_id = {
                item.sample_id: item
                for item in load_benchmark_cases(benchmark, settings=settings)
            }
            n_runs = source_run.n_runs or 1
        missing = next(
            (sample_id for sample_id in ordered_ids if sample_id not in current_by_id),
            None,
        )
        if missing is not None:
            raise ValueError(f"用例 {missing} 已不在当前 benchmark 中，无法重新评测")
        selected = [current_by_id[sample_id] for sample_id in ordered_ids]
        progress.set_case_ids(ordered_ids)

        config = prepare_run_config(
            settings,
            run_name=src_slug,
            repeat=n_runs,
            judge_ov=judge_ov,
            adapter_ov=adapter_ov,
        )
        with session_scope() as session:
            source_run = session.get(EvalRun, run_id)
            if source_run is None:
                raise ValueError(f"run {run_id} 不存在")
            scoring_standard = source_run.scoring_standard
        adapter = build_eval_adapter(config)
        judges = build_judge_stack(config, scoring_standard=scoring_standard)
        # 每条 Case 判完立即写入。前端轮询 case_result 后会看到新的分数/结论，
        # 不必等待整批 Case 都结束。
        progress.set_case_complete_callback(IncrementalRetryPersister(run_id))
        retried = await ej.evaluate(
            config,
            selected,
            adapter,
            judges,
            progress=progress,
            run_name=src_slug,
            account_owner=str(run_id),
            scoring_standard=scoring_standard,
        )
        await enrich_report_agent_chains(retried, settings)
        for result in retried.results:
            refresh_result_assertions(result)
        apply_grading(retried.results, scoring_standard)
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
