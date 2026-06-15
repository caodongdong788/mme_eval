"""Pairwise 对比路由：发起 / 可比性预检 / 查询（OpenSpec change add-pairwise-comparison）。

只卡判分尺子、放开被测 bot；产出相对偏好，不进任何 gate。
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..db import get_session
from ..models_db import FeishuUser, PairwiseComparison
from ..pairwise_job import run_pairwise_comparison
from ..schemas import (
    PairwiseCalibrateUpdate,
    PairwiseCaseVerdictOut,
    PairwiseComparabilityOut,
    PairwiseComparisonOut,
    PairwiseCreate,
    PairwiseDetailOut,
    PairwiseNoteUpdate,
)
from ..services import pairwise as pw_svc

router = APIRouter(prefix="/api/compare", tags=["compare"])


@router.get("/pairwise/precheck", response_model=PairwiseComparabilityOut)
def precheck_pairwise(
    run_a_id: int = Query(...),
    run_b_id: int = Query(...),
    session: Session = Depends(get_session),
) -> PairwiseComparabilityOut:
    """可比性预检：供前端在发起前给出中文提示。"""
    return pw_svc.precheck_pairwise(session, run_a_id, run_b_id)


@router.post("/pairwise", response_model=PairwiseComparisonOut, status_code=201)
async def create_pairwise(
    payload: PairwiseCreate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> PairwiseComparison:
    created_by = current_user.name if current_user is not None else None
    comp = pw_svc.create_pairwise_record(session, payload, created_by=created_by)
    asyncio.create_task(run_pairwise_comparison(comp.id, payload.judge_model_id))
    return comp


@router.patch("/pairwise/{comparison_id}", response_model=PairwiseComparisonOut)
def update_pairwise_note(
    comparison_id: int,
    payload: PairwiseNoteUpdate,
    session: Session = Depends(get_session),
) -> PairwiseComparison:
    """二次编辑对比备注（仅改 note，不触碰判分/汇总）。"""
    return pw_svc.update_pairwise_note(session, comparison_id, payload.note)


@router.delete("/pairwise/{comparison_id}", status_code=204)
def delete_pairwise(
    comparison_id: int, session: Session = Depends(get_session)
) -> None:
    """删除一次对比，级联删其全部逐用例结论（verdicts 关系 cascade）。"""
    pw_svc.delete_pairwise(session, comparison_id)


@router.get("/pairwise", response_model=list[PairwiseComparisonOut])
def list_pairwise(
    run_id: Optional[int] = Query(None),
    session: Session = Depends(get_session),
) -> list[PairwiseComparison]:
    return pw_svc.list_pairwise_comparisons(session, run_id)


@router.get("/pairwise/{comparison_id}", response_model=PairwiseDetailOut)
def get_pairwise(
    comparison_id: int, session: Session = Depends(get_session)
) -> PairwiseDetailOut:
    return pw_svc.get_pairwise_detail(session, comparison_id)


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
    calibrated_by = current_user.name if current_user else None
    return pw_svc.calibrate_pairwise_verdict(
        session, comparison_id, sample_id, payload, calibrated_by=calibrated_by
    )


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
    return pw_svc.reset_pairwise_calibration(session, comparison_id, sample_id)
