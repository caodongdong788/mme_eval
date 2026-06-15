"""runs 人工审核队列（HITL）。"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from ...auth import get_current_user_optional
from ...db import get_session
from ...models_db import CaseAnnotation, FeishuUser
from ...schemas import (
    AnnotateRequest,
    AnnotationOut,
    ReviewQueueItemOut,
    ReviewStatsOut,
)
from ...services import review as review_svc
from ._router import router


@router.get("/{run_id}/review-queue", response_model=list[ReviewQueueItemOut])
def get_review_queue(
    run_id: int,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    score_profile: Optional[str] = None,
    session: Session = Depends(get_session),
) -> list[ReviewQueueItemOut]:
    return review_svc.get_review_queue(
        session,
        run_id,
        level=level,
        release_passed=release_passed,
        stability=stability,
        scenario=scenario,
        score_profile=score_profile,
    )


@router.get(
    "/{run_id}/cases/{sample_id}/annotations",
    response_model=list[AnnotationOut],
)
def get_case_annotations(
    run_id: int, sample_id: str, session: Session = Depends(get_session)
) -> list[CaseAnnotation]:
    return review_svc.list_case_annotations(session, run_id, sample_id)


@router.post(
    "/{run_id}/cases/{sample_id}/annotate",
    response_model=AnnotationOut,
    status_code=201,
)
def annotate_case(
    run_id: int,
    sample_id: str,
    payload: AnnotateRequest,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> CaseAnnotation:
    reviewer = current_user.name if current_user else None
    return review_svc.annotate_case(
        session, run_id, sample_id, payload, reviewer=reviewer
    )


@router.get("/{run_id}/review-stats", response_model=ReviewStatsOut)
def get_review_stats(
    run_id: int, session: Session = Depends(get_session)
) -> ReviewStatsOut:
    return review_svc.get_review_stats(session, run_id)
