"""Pairwise 对比路由：发起 / 可比性预检 / 查询（OpenSpec change add-pairwise-comparison）。

只卡判分尺子、放开被测 bot；产出相对偏好，不进任何 gate。
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..compare import check_pairwise_comparable, pairwise_subject_diff
from ..db import get_session
from ..models_db import (
    EvalRun,
    FeishuUser,
    JudgeModelConfig,
    PairwiseCaseVerdict,
    PairwiseComparison,
)
from ..pairwise_job import (
    _DIMENSIONS,
    pairwise_verdict_to_out,
    recompute_pairwise_summary,
    run_pairwise_comparison,
)
from ..schemas import (
    PairwiseCalibrateUpdate,
    PairwiseCaseVerdictOut,
    PairwiseComparabilityOut,
    PairwiseComparisonOut,
    PairwiseCreate,
    PairwiseDetailOut,
    PairwiseNoteUpdate,
)

router = APIRouter(prefix="/api/compare", tags=["compare"])


def _get_run_or_404(session: Session, run_id: int, label: str) -> EvalRun:
    run = session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"评测 {label}（run {run_id}）不存在")
    return run


def _run_display_name(run: EvalRun | None, run_id: int) -> str:
    """评测显示名：name → run_slug → #id 兜底。"""
    if run is not None and (run.name or "").strip():
        return run.name
    if run is not None and (run.run_slug or "").strip():
        return run.run_slug
    return f"#{run_id}"


def _attach_run_names(session: Session, comps: list[PairwiseComparison]) -> None:
    """给对比记录挂上 A/B 评测显示名（瞬态属性，供响应模型读取，不入库）。"""
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


@router.get("/pairwise/precheck", response_model=PairwiseComparabilityOut)
def precheck_pairwise(
    run_a_id: int = Query(...),
    run_b_id: int = Query(...),
    session: Session = Depends(get_session),
) -> PairwiseComparabilityOut:
    """可比性预检：供前端在发起前给出中文提示。"""
    run_a = _get_run_or_404(session, run_a_id, "A")
    run_b = _get_run_or_404(session, run_b_id, "B")
    reasons = check_pairwise_comparable(session, run_a, run_b)
    return PairwiseComparabilityOut(
        comparable=not reasons,
        reasons=reasons,
        subject_diff=pairwise_subject_diff(run_a, run_b),
    )


@router.post("/pairwise", response_model=PairwiseComparisonOut, status_code=201)
async def create_pairwise(
    payload: PairwiseCreate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> PairwiseComparison:
    run_a = _get_run_or_404(session, payload.run_a_id, "A")
    run_b = _get_run_or_404(session, payload.run_b_id, "B")
    jm = session.get(JudgeModelConfig, payload.judge_model_id)
    if jm is None:
        raise HTTPException(
            status_code=404, detail=f"判分模型 {payload.judge_model_id} 不存在"
        )

    reasons = check_pairwise_comparable(session, run_a, run_b)
    if reasons:
        raise HTTPException(status_code=422, detail="；".join(reasons))

    comp = PairwiseComparison(
        run_a_id=run_a.id,
        run_b_id=run_b.id,
        judge_model=jm.model or jm.name,
        note=(payload.note or "").strip(),
        status="running",
        scope=payload.scope,
        subject_diff=pairwise_subject_diff(run_a, run_b),
        created_by=current_user.name if current_user is not None else None,
    )
    session.add(comp)
    session.flush()
    session.commit()  # 让后台任务能在独立会话里看到这一行
    comp_id = comp.id

    asyncio.create_task(run_pairwise_comparison(comp_id, payload.judge_model_id))
    _attach_run_names(session, [comp])
    return comp


@router.patch("/pairwise/{comparison_id}", response_model=PairwiseComparisonOut)
def update_pairwise_note(
    comparison_id: int,
    payload: PairwiseNoteUpdate,
    session: Session = Depends(get_session),
) -> PairwiseComparison:
    """二次编辑对比备注（仅改 note，不触碰判分/汇总）。"""
    comp = session.get(PairwiseComparison, comparison_id)
    if comp is None:
        raise HTTPException(status_code=404, detail=f"对比 {comparison_id} 不存在")
    comp.note = (payload.note or "").strip()
    session.flush()
    _attach_run_names(session, [comp])
    return comp


@router.delete("/pairwise/{comparison_id}", status_code=204)
def delete_pairwise(
    comparison_id: int, session: Session = Depends(get_session)
) -> None:
    """删除一次对比，级联删其全部逐用例结论（verdicts 关系 cascade）。"""
    comp = session.get(PairwiseComparison, comparison_id)
    if comp is None:
        raise HTTPException(status_code=404, detail=f"对比 {comparison_id} 不存在")
    session.delete(comp)


@router.get("/pairwise", response_model=list[PairwiseComparisonOut])
def list_pairwise(
    run_id: Optional[int] = None,
    session: Session = Depends(get_session),
) -> list[PairwiseComparison]:
    stmt = select(PairwiseComparison).order_by(PairwiseComparison.id.desc())
    if run_id is not None:
        stmt = stmt.where(
            (PairwiseComparison.run_a_id == run_id)
            | (PairwiseComparison.run_b_id == run_id)
        )
    comps = list(session.execute(stmt).scalars().all())
    _attach_run_names(session, comps)
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


@router.get("/pairwise/{comparison_id}", response_model=PairwiseDetailOut)
def get_pairwise(
    comparison_id: int, session: Session = Depends(get_session)
) -> PairwiseDetailOut:
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
    _attach_run_names(session, [comp])
    base = PairwiseComparisonOut.model_validate(comp)
    return PairwiseDetailOut(
        **base.model_dump(),
        verdicts=[pairwise_verdict_to_out(v) for v in verdicts],
    )


@router.patch(
    "/pairwise/{comparison_id}/cases/{sample_id}",
    response_model=PairwiseCaseVerdictOut,
)
def calibrate_pairwise_verdict(
    comparison_id: int,
    sample_id: str,
    payload: PairwiseCalibrateUpdate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> PairwiseCaseVerdictOut:
    """人工校准：覆写有效结论/维度/理由，并重算对比汇总。"""
    from datetime import datetime

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
    row.human_calibrated_by = current_user.name if current_user else None
    row.human_calibrated_at = datetime.utcnow()
    session.flush()
    recompute_pairwise_summary(session, comparison_id)
    return pairwise_verdict_to_out(row)


@router.delete(
    "/pairwise/{comparison_id}/cases/{sample_id}",
    response_model=PairwiseCaseVerdictOut,
)
def reset_pairwise_calibration(
    comparison_id: int,
    sample_id: str,
    session: Session = Depends(get_session),
) -> PairwiseCaseVerdictOut:
    """恢复机器判定并重算汇总。"""
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
