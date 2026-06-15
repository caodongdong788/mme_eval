"""RunReport → 数据库落库器。

把 ``RunReport`` 的 run 级汇总写入 ``eval_run`` 标量/JSON 列，每条 ``CaseResult`` 拆成
``case_result`` 的可筛选标量列 + 完整 ``detail_json``。判分核心零依赖（只读 RunReport）。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from medeval.models import CaseResult, RunReport

from .models_db import CaseResultRow, EvalRun


def _enum_val(v) -> str:
    """枚举取 .value，其它转 str。"""
    return getattr(v, "value", v) if v is not None else ""


def _case_token_cost(cr: CaseResult, pricing: dict | None) -> tuple[int | None, float | None]:
    """从一条 CaseResult 算 (总 token, 成本)。仅观测、不否决。

    总 token 优先取 ``per_run_tokens`` 之和，回退到代表性 trace 逐轮求和；无任何 usage
    返回 (None, None)。成本仅在配置非零单价时折算（input/output 分别计价），否则 None。
    """
    usage = getattr(cr.trace, "turn_token_usage", []) if cr.trace else []
    if cr.per_run_tokens:
        total = sum(int(t) for t in cr.per_run_tokens)
    else:
        total = sum(int(u.get("total_tokens", 0)) for u in usage)
    if total == 0 and not usage:
        return None, None
    pricing = pricing or {}
    in_price = float(pricing.get("input_per_million", 0.0) or 0.0)
    out_price = float(pricing.get("output_per_million", 0.0) or 0.0)
    cost: float | None = None
    if in_price > 0 or out_price > 0:
        prompt = sum(int(u.get("prompt_tokens", 0)) for u in usage)
        completion = sum(int(u.get("completion_tokens", 0)) for u in usage)
        cost = prompt / 1_000_000 * in_price + completion / 1_000_000 * out_price
    return total, cost


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
    row.hard_gate_failed = report.hard_gate_failed
    row.n_runs = report.n_runs
    row.started_at = report.started_at
    row.finished_at = report.finished_at
    row.grading = report.grading
    row.stability_distribution = report.stability_distribution
    row.latency_summary = report.latency_summary
    row.token_summary = report.token_summary
    row.pass_rate_ci = report.pass_rate_ci
    row.guideline_match = report.guideline_match
    row.failure_tag_counter = report.failure_tag_counter
    row.judge_fingerprints = report.judge_fingerprints
    row.by_level = report.by_level
    row.by_scenario = report.by_scenario
    row.config_snapshot = report.config_snapshot


def build_case_row(
    run_id: int, cr: CaseResult, pricing: dict | None = None
) -> CaseResultRow:
    """从一条 CaseResult 构造 case_result 行（标量列 + detail_json）。"""
    case = cr.case
    total_tokens, cost = _case_token_cost(cr, pricing)
    return CaseResultRow(
        run_id=run_id,
        sample_id=case.sample_id,
        scenario=case.scenario,
        sub_scenario=case.sub_scenario,
        level=_enum_val(case.level),
        source=_enum_val(case.source),
        tags=[],
        hard_gate_passed=cr.hard_gate_passed,
        gate_passed=cr.gate_passed,
        release_passed=cr.release_passed,
        composite_score=cr.composite_score,
        grade=cr.grade,
        score_profile=cr.score_profile,
        soft_score=cr.soft_score,
        soft_score_max=cr.soft_score_max,
        stability=cr.stability,
        needs_human_review=cr.needs_human_review,
        guideline_match_rate=cr.guideline_match_rate,
        latency_ms=float(cr.trace.duration_ms) if cr.trace else None,
        total_tokens=total_tokens,
        cost=cost,
        failure_tags=list(cr.failure_tags),
        detail_json=cr.model_dump(mode="json"),
    )


def attach_case_results(session: Session, run_id: int, report: RunReport) -> None:
    """把 report 的所有用例结果作为 case_result 行加入会话。"""
    pricing = (report.config_snapshot or {}).get("cost")
    for cr in report.results:
        session.add(build_case_row(run_id, cr, pricing))


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
