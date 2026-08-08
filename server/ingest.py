"""RunReport → 数据库落库器。

把 ``RunReport`` 的 run 级汇总写入 ``eval_run`` 标量/JSON 列，每条 ``CaseResult`` 拆成
``case_result`` 的可筛选标量列 + 完整 ``detail_json``。判分核心零依赖（只读 RunReport）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.models import CaseResult, RunReport
from medeval.config import redact_config_secrets
from medeval.reporter.token_cost import case_token_cost

from .models_db import CaseResultRow, EvalRun
from .services.case_query import (
    case_n_turns_from_detail,
    case_rag_status_from_detail,
    case_ttft_ms_from_detail,
)


CASE_RESULT_MUTABLE_FIELDS = tuple(
    column.name
    for column in CaseResultRow.__table__.columns
    if column.name not in {"id", "run_id"}
)


def _enum_val(v) -> str:
    """枚举取 .value，其它转 str。"""
    return getattr(v, "value", v) if v is not None else ""


def populate_run_summary(row: EvalRun, report: RunReport) -> None:
    """把 RunReport 的汇总字段写入（已存在的）EvalRun 行。"""
    row.run_slug = report.run_name
    if not row.name:
        row.name = report.run_name
    if report.description:
        row.description = report.description
    row.adapter_type = report.adapter_type
    row.total = report.total
    row.passed = report.passed
    row.pass_rate = (report.passed / report.total) if report.total else 0.0
    row.medical_safety_failed = report.medical_safety_failed
    row.n_runs = report.n_runs
    row.started_at = report.started_at
    row.finished_at = report.finished_at
    row.grading = {**(report.grading or {}), "reliability": report.reliability}
    row.stability_distribution = report.stability_distribution
    row.latency_summary = report.latency_summary
    row.ttft_summary = report.ttft_summary
    row.token_summary = report.token_summary
    row.pass_rate_ci = report.pass_rate_ci
    row.guideline_match = report.guideline_match
    row.failure_tag_counter = report.failure_tag_counter
    row.judge_fingerprints = report.judge_fingerprints
    row.by_level = report.by_level
    row.by_scenario = report.by_scenario
    row.by_case_type = report.by_case_type
    row.config_snapshot = redact_config_secrets(report.config_snapshot)


def build_case_row(
    run_id: int, cr: CaseResult, pricing: dict | None = None
) -> CaseResultRow:
    """从一条 CaseResult 构造 case_result 行（标量列 + detail_json）。"""
    case = cr.case
    total_tokens, cost = case_token_cost(cr, pricing)
    applicable_guidelines = [item for item in cr.guideline_scores if item.get("applicable", True)]
    guideline_earned = sum(float(item.get("score", 0)) for item in applicable_guidelines)
    guideline_max = sum(float(item.get("max_score", 0)) for item in applicable_guidelines)
    detail = cr.model_dump(mode="json")
    return CaseResultRow(
        run_id=run_id,
        sample_id=case.sample_id,
        scenario=case.scenario,
        case_type=case.case_type,
        sub_scenario="",
        level=_enum_val(case.level),
        source=_enum_val(case.source),
        tags=[],
        medical_safety_passed=cr.medical_safety_passed,
        release_passed=cr.release_passed,
        composite_score=cr.composite_score,
        guideline_earned=guideline_earned if guideline_max > 0 else None,
        guideline_max=guideline_max if guideline_max > 0 else None,
        grade=cr.grade,
        stability=cr.stability,
        latency_ms=float(cr.trace.duration_ms) if cr.trace else None,
        ttft_ms=case_ttft_ms_from_detail(detail),
        total_tokens=total_tokens,
        cost=cost,
        n_turns=case_n_turns_from_detail(detail),
        rag_status=case_rag_status_from_detail(detail),
        failure_tags=list(cr.failure_tags),
        detail_json=detail,
    )


def update_case_row(target: CaseResultRow, replacement: CaseResultRow) -> CaseResultRow:
    """把计算结果复制到已有 ORM 行，保留数据库主键。"""
    for field in CASE_RESULT_MUTABLE_FIELDS:
        setattr(target, field, getattr(replacement, field))
    return target


def upsert_case_result(
    session: Session,
    run_id: int,
    result: CaseResult,
    pricing: dict | None = None,
) -> CaseResultRow:
    """按 ``run_id + sample_id`` 幂等写入单条结果。"""
    replacement = build_case_row(run_id, result, pricing)
    existing = session.execute(
        select(CaseResultRow)
        .where(
            CaseResultRow.run_id == run_id,
            CaseResultRow.sample_id == result.case.sample_id,
        )
        .order_by(CaseResultRow.id)
    ).scalars().first()
    if existing is None:
        session.add(replacement)
        return replacement
    return update_case_row(existing, replacement)


def attach_case_results(session: Session, run_id: int, report: RunReport) -> None:
    """幂等写入 report 的所有用例结果，兼容运行中的增量结果。"""
    pricing = (report.config_snapshot or {}).get("cost")
    for cr in report.results:
        upsert_case_result(session, run_id, cr, pricing)


def finalize_run(session: Session, row: EvalRun, report: RunReport) -> EvalRun:
    """评测完成：填 run 汇总 + 落 case 结果 + 置 success。调用方负责 commit。"""
    populate_run_summary(row, report)
    row.status = "success"
    row.error_msg = ""
    session.flush()  # 确保 row.id 可用
    attach_case_results(session, row.id, report)
    return row


def ingest_report(
    session: Session,
    report: RunReport,
    *,
    benchmark_id: int | None = None,
    judge_overrides: dict | None = None,
    adapter_overrides: dict | None = None,
    created_by: str | None = None,
) -> EvalRun:
    """新建一个 success 的 EvalRun 并落库（用于历史导入与测试）。返回已 flush 的行。"""
    row = EvalRun(
        run_slug=report.run_name,
        name=report.run_name,
        status="pending",
        benchmark_id=benchmark_id,
        judge_overrides=judge_overrides or {},
        adapter_overrides=adapter_overrides or {},
        created_by=created_by,
    )
    session.add(row)
    finalize_run(session, row, report)
    return row
