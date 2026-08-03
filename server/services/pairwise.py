"""Pairwise 对比 HTTP 侧业务（发起/查询/校准）；执行见 pairwise_job。"""

from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..compare import check_pairwise_comparable, pairwise_rag_side, pairwise_subject_diff
from ..models_db import (
    CaseResultRow,
    EvalRun,
    JudgeModelConfig,
    PairwiseCaseVerdict,
    PairwiseComparison,
)
from ..pairwise_job import (
    _DIMENSIONS,
    pairwise_verdict_to_out,
    recompute_pairwise_summary,
)
from ..schemas import (
    PairwiseCalibrateUpdate,
    PairwiseCaseVerdictOut,
    PairwiseComparabilityOut,
    PairwiseComparisonOut,
    PairwiseCreate,
    PairwiseDetailOut,
)
from .case_query import RAG_TRIGGERED_STATUSES


def get_eval_run_or_404(session: Session, run_id: int, label: str) -> EvalRun:
    run = session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"评测 {label}（run {run_id}）不存在")
    return run


def _run_display_name(run: EvalRun | None, run_id: int) -> str:
    if run is not None and (run.name or "").strip():
        return run.name
    if run is not None and (run.run_slug or "").strip():
        return run.run_slug
    return f"#{run_id}"


def attach_run_names(session: Session, comps: list[PairwiseComparison]) -> None:
    ids = {c.run_a_id for c in comps} | {c.run_b_id for c in comps}
    runs = {
        r.id: r
        for r in session.execute(
            select(EvalRun).where(EvalRun.id.in_(ids))
        ).scalars().all()
    } if ids else {}
    for c in comps:
        c.run_a_name = _run_display_name(runs.get(c.run_a_id), c.run_a_id)
        c.run_b_name = _run_display_name(runs.get(c.run_b_id), c.run_b_id)


def precheck_pairwise(
    session: Session, run_a_id: int, run_b_id: int
) -> PairwiseComparabilityOut:
    run_a = get_eval_run_or_404(session, run_a_id, "A")
    run_b = get_eval_run_or_404(session, run_b_id, "B")
    reasons = check_pairwise_comparable(session, run_a, run_b)
    return PairwiseComparabilityOut(
        comparable=not reasons,
        reasons=reasons,
        subject_diff=pairwise_subject_diff(run_a, run_b),
        rag_analysis=_pairwise_rag_analysis(session, run_a, run_b),
    )


def _pairwise_rag_analysis(
    session: Session, run_a: EvalRun, run_b: EvalRun
) -> dict[str, object]:
    """预检阶段汇总两侧真实 RAG 状态，帮助用户判断筛选后还剩多少题。"""

    def _status_map(run_id: int) -> dict[str, str]:
        rows = session.execute(
            select(CaseResultRow.sample_id, CaseResultRow.rag_status).where(
                CaseResultRow.run_id == run_id
            )
        ).all()
        return {sid: str(status or "unknown") for sid, status in rows}

    map_a = _status_map(run_a.id)
    map_b = _status_map(run_b.id)
    common = sorted(set(map_a) & set(map_b))
    counts_a = Counter(map_a[sid] for sid in common)
    counts_b = Counter(map_b[sid] for sid in common)
    rag_side = pairwise_rag_side(run_a, run_b)
    rag_counts = counts_a if rag_side == "A" else counts_b if rag_side == "B" else Counter()
    baseline_counts = counts_b if rag_side == "A" else counts_a if rag_side == "B" else Counter()
    selected = sum(rag_counts[status] for status in RAG_TRIGGERED_STATUSES)
    return {
        "rag_side": rag_side,
        "common_cases": len(common),
        "selected_cases": selected,
        "excluded_cases": len(common) - selected,
        "unknown_cases": rag_counts["unknown"],
        "baseline_triggered_cases": sum(
            baseline_counts[status] for status in RAG_TRIGGERED_STATUSES
        ),
        "a_status_counts": dict(counts_a),
        "b_status_counts": dict(counts_b),
    }


def create_pairwise_record(
    session: Session,
    payload: PairwiseCreate,
    *,
    created_by: Optional[str],
) -> PairwiseComparison:
    run_a = get_eval_run_or_404(session, payload.run_a_id, "A")
    run_b = get_eval_run_or_404(session, payload.run_b_id, "B")
    jm = session.get(JudgeModelConfig, payload.judge_model_id)
    if jm is None:
        raise HTTPException(
            status_code=404, detail=f"判分模型 {payload.judge_model_id} 不存在"
        )

    reasons = check_pairwise_comparable(session, run_a, run_b)
    if reasons:
        raise HTTPException(status_code=422, detail="；".join(reasons))
    if payload.scope == "rag_triggered_only":
        rag_analysis = _pairwise_rag_analysis(session, run_a, run_b)
        if rag_analysis["rag_side"] is None:
            raise HTTPException(
                status_code=422,
                detail="无法自动识别 RAG 侧：请确保两次评测中恰好一侧开启 RAG。",
            )
        if int(rag_analysis["selected_cases"]) == 0:
            raise HTTPException(
                status_code=422,
                detail="RAG 侧没有检测到真实 RAG 调用，无法按该范围发起对比。",
            )

    comp = PairwiseComparison(
        run_a_id=run_a.id,
        run_b_id=run_b.id,
        judge_model=jm.model or jm.name,
        note=(payload.note or "").strip(),
        status="running",
        scope=payload.scope,
        subject_diff=pairwise_subject_diff(run_a, run_b),
        created_by=created_by,
    )
    session.add(comp)
    session.flush()
    session.commit()
    attach_run_names(session, [comp])
    return comp


def update_pairwise_note(
    session: Session, comparison_id: int, note: str
) -> PairwiseComparison:
    comp = session.get(PairwiseComparison, comparison_id)
    if comp is None:
        raise HTTPException(status_code=404, detail=f"对比 {comparison_id} 不存在")
    comp.note = (note or "").strip()
    session.flush()
    attach_run_names(session, [comp])
    return comp


def delete_pairwise(session: Session, comparison_id: int) -> None:
    comp = session.get(PairwiseComparison, comparison_id)
    if comp is None:
        raise HTTPException(status_code=404, detail=f"对比 {comparison_id} 不存在")
    session.delete(comp)


def list_pairwise_comparisons(
    session: Session, run_id: Optional[int] = None
) -> list[PairwiseComparison]:
    stmt = select(PairwiseComparison).order_by(PairwiseComparison.id.desc())
    if run_id is not None:
        stmt = stmt.where(
            (PairwiseComparison.run_a_id == run_id)
            | (PairwiseComparison.run_b_id == run_id)
        )
    comps = list(session.execute(stmt).scalars().all())
    attach_run_names(session, comps)
    return comps


def _get_verdict_or_404(
    session: Session, comparison_id: int, sample_id: str
) -> PairwiseCaseVerdict:
    row = session.execute(
        select(PairwiseCaseVerdict).where(
            PairwiseCaseVerdict.comparison_id == comparison_id,
            PairwiseCaseVerdict.sample_id == sample_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"对比 {comparison_id} 下用例 {sample_id} 不存在",
        )
    return row


def get_pairwise_detail(session: Session, comparison_id: int) -> PairwiseDetailOut:
    comp = session.get(PairwiseComparison, comparison_id)
    if comp is None:
        raise HTTPException(status_code=404, detail=f"对比 {comparison_id} 不存在")
    verdicts = list(
        session.execute(
            select(PairwiseCaseVerdict)
            .where(PairwiseCaseVerdict.comparison_id == comparison_id)
            .order_by(PairwiseCaseVerdict.id)
        ).scalars().all()
    )
    attach_run_names(session, [comp])
    run_a = session.get(EvalRun, comp.run_a_id)
    run_b = session.get(EvalRun, comp.run_b_id)
    sample_ids = [v.sample_id for v in verdicts]

    def _rag_map(run_id: int) -> dict[str, str]:
        if not sample_ids:
            return {}
        rows = session.execute(
            select(CaseResultRow.sample_id, CaseResultRow.rag_status).where(
                CaseResultRow.run_id == run_id,
                CaseResultRow.sample_id.in_(sample_ids),
            )
        ).all()
        return {sid: str(status or "unknown") for sid, status in rows}

    rag_a = _rag_map(comp.run_a_id)
    rag_b = _rag_map(comp.run_b_id)

    def _scoped_observability(run_id: int) -> dict[str, dict[str, object]]:
        """RAG 子集观测；Case 标量是每题代表性会话，避免读取大型 detail_json。"""
        if not sample_ids:
            return {"latency_summary": {}, "token_summary": {}}
        rows = session.execute(
            select(CaseResultRow.latency_ms, CaseResultRow.total_tokens).where(
                CaseResultRow.run_id == run_id,
                CaseResultRow.sample_id.in_(sample_ids),
            )
        ).all()
        latencies = sorted(float(latency) for latency, _ in rows if latency is not None)
        tokens = [int(total) for _, total in rows if total is not None]
        latency_summary: dict[str, object] = {}
        if latencies:
            p90_index = max(0, min(len(latencies) - 1, round(0.9 * (len(latencies) - 1))))
            latency_summary = {
                "count": len(latencies),
                "avg_ms": sum(latencies) / len(latencies),
                "median_ms": statistics.median(latencies),
                "p90_ms": latencies[p90_index],
                "max_ms": latencies[-1],
            }
        token_summary: dict[str, object] = {}
        if tokens:
            token_total = sum(tokens)
            token_summary = {
                "count": len(tokens),
                "total_tokens": token_total,
                "avg_tokens_per_run": token_total / len(tokens),
            }
        return {"latency_summary": latency_summary, "token_summary": token_summary}

    if comp.scope == "rag_triggered_only":
        observability_a = _scoped_observability(comp.run_a_id)
        observability_b = _scoped_observability(comp.run_b_id)
    else:
        observability_a = {
            "latency_summary": dict(run_a.latency_summary or {}) if run_a else {},
            "token_summary": dict(run_a.token_summary or {}) if run_a else {},
        }
        observability_b = {
            "latency_summary": dict(run_b.latency_summary or {}) if run_b else {},
            "token_summary": dict(run_b.token_summary or {}) if run_b else {},
        }
    base = PairwiseComparisonOut.model_validate(comp)
    return PairwiseDetailOut(
        **base.model_dump(),
        verdicts=[
            pairwise_verdict_to_out(
                v,
                rag_status_a=rag_a.get(v.sample_id, "unknown"),
                rag_status_b=rag_b.get(v.sample_id, "unknown"),
            )
            for v in verdicts
        ],
        run_a_observability=observability_a,
        run_b_observability=observability_b,
    )


def calibrate_pairwise_verdict(
    session: Session,
    comparison_id: int,
    sample_id: str,
    payload: PairwiseCalibrateUpdate,
    *,
    calibrated_by: Optional[str],
) -> PairwiseCaseVerdictOut:
    comp = session.get(PairwiseComparison, comparison_id)
    if comp is None:
        raise HTTPException(status_code=404, detail=f"对比 {comparison_id} 不存在")
    if comp.status != "done":
        raise HTTPException(status_code=422, detail="仅已完成的对比可人工校准")
    row = _get_verdict_or_404(session, comparison_id, sample_id)

    dims: dict[str, str] = {}
    for dim in _DIMENSIONS:
        val = (payload.dimension_winners or {}).get(dim, "tie")
        if val not in ("A", "B", "tie"):
            val = "tie"
        dims[dim] = val

    row.human_calibrated = True
    row.human_winner = payload.winner
    row.human_dimension_winners = dims
    row.human_reason = (payload.reason or "").strip()
    row.human_calibrated_by = calibrated_by
    row.human_calibrated_at = datetime.utcnow()
    session.flush()
    recompute_pairwise_summary(session, comparison_id)
    return pairwise_verdict_to_out(row)


def reset_pairwise_calibration(
    session: Session, comparison_id: int, sample_id: str
) -> PairwiseCaseVerdictOut:
    comp = session.get(PairwiseComparison, comparison_id)
    if comp is None:
        raise HTTPException(status_code=404, detail=f"对比 {comparison_id} 不存在")
    row = _get_verdict_or_404(session, comparison_id, sample_id)
    row.human_calibrated = False
    row.human_winner = ""
    row.human_dimension_winners = {}
    row.human_reason = ""
    row.human_calibrated_by = None
    row.human_calibrated_at = None
    session.flush()
    recompute_pairwise_summary(session, comparison_id)
    return pairwise_verdict_to_out(row)
