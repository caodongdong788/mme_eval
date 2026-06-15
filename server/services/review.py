"""人工审核队列（HITL）业务逻辑。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_db import CaseAnnotation
from ..schemas import (
    AnnotateRequest,
    AnnotationOut,
    ReviewQueueItemOut,
    ReviewStatsOut,
)
from .case_query import case_row_or_404, filtered_case_rows, queue_reasons
from .runs import get_run_or_404


def _annotations_by_sample(session: Session, run_id: int) -> dict[str, list[CaseAnnotation]]:
    by_sample: dict[str, list[CaseAnnotation]] = {}
    for a in session.execute(
        select(CaseAnnotation)
        .where(CaseAnnotation.run_id == run_id)
        .order_by(CaseAnnotation.created_at)
    ).scalars().all():
        by_sample.setdefault(a.sample_id, []).append(a)
    return by_sample


def get_review_queue(
    session: Session,
    run_id: int,
    *,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    score_profile: Optional[str] = None,
) -> list[ReviewQueueItemOut]:
    get_run_or_404(session, run_id)
    rows = filtered_case_rows(
        session,
        run_id,
        level=level,
        release_passed=release_passed,
        stability=stability,
        scenario=scenario,
        score_profile=score_profile,
    )
    anns_by_sample = _annotations_by_sample(session, run_id)

    items: list[ReviewQueueItemOut] = []
    for r in rows:
        reasons = queue_reasons(r)
        if not reasons:
            continue
        anns = anns_by_sample.get(r.sample_id, [])
        items.append(
            ReviewQueueItemOut(
                sample_id=r.sample_id,
                scenario=r.scenario,
                level=r.level,
                release_passed=r.release_passed,
                composite_score=r.composite_score,
                failure_tags=list(r.failure_tags or []),
                reasons=reasons,
                reviewed=bool(anns),
                annotations=[AnnotationOut.model_validate(a) for a in anns],
            )
        )
    return items


def list_case_annotations(
    session: Session, run_id: int, sample_id: str
) -> list[CaseAnnotation]:
    return list(
        session.execute(
            select(CaseAnnotation)
            .where(
                CaseAnnotation.run_id == run_id,
                CaseAnnotation.sample_id == sample_id,
            )
            .order_by(CaseAnnotation.created_at)
        )
        .scalars()
        .all()
    )


def annotate_case(
    session: Session,
    run_id: int,
    sample_id: str,
    payload: AnnotateRequest,
    *,
    reviewer: Optional[str],
) -> CaseAnnotation:
    case_row_or_404(session, run_id, sample_id)
    ann = CaseAnnotation(
        run_id=run_id,
        sample_id=sample_id,
        reviewer=reviewer,
        verdict=payload.verdict,
        suggestion=payload.suggestion,
        comment=payload.comment,
    )
    session.add(ann)
    session.flush()
    return ann


def get_review_stats(session: Session, run_id: int) -> ReviewStatsOut:
    get_run_or_404(session, run_id)
    rows = filtered_case_rows(session, run_id)
    queued = [r.sample_id for r in rows if queue_reasons(r)]
    queue_total = len(queued)

    latest: dict[str, str] = {}
    for a in session.execute(
        select(CaseAnnotation)
        .where(CaseAnnotation.run_id == run_id)
        .order_by(CaseAnnotation.created_at)
    ).scalars().all():
        if a.sample_id in queued:
            latest[a.sample_id] = a.verdict

    reviewed = len(latest)
    agree = sum(1 for v in latest.values() if v == "agree")
    override = sum(1 for v in latest.values() if v == "override")
    return ReviewStatsOut(
        queue_total=queue_total,
        reviewed=reviewed,
        pending=queue_total - reviewed,
        agree=agree,
        override=override,
        agree_rate=(agree / reviewed) if reviewed else 0.0,
        disagree_rate=(override / reviewed) if reviewed else 0.0,
    )
