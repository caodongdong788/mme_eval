"""用例结果查询、派生展示字段与 HITL 队列辅助。"""

from __future__ import annotations

from typing import Any, Optional

import yaml
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session, load_only

from ..models_db import CaseAnnotation, CaseResultRow
from ..schemas import CaseScores, ReviewSummary

_LIST_CASE_COLUMNS = tuple(
    getattr(CaseResultRow, attr.key)
    for attr in sa_inspect(CaseResultRow).column_attrs
    if attr.key != "detail_json"
)


def _attach_row_display_fields(row: CaseResultRow, *, load_detail_json: bool) -> None:
    if load_detail_json:
        row.n_turns = case_n_turns(row)
        row.langfuse_trace_url = case_trace_url(row)
        gc = guideline_counts(row)
        row.guideline_earned = gc[0] if gc else None
        row.guideline_max = gc[1] if gc else None
    else:
        row.n_turns = 1
        row.langfuse_trace_url = None


def case_n_turns(row: CaseResultRow) -> int:
    detail = row.detail_json or {}
    case = detail.get("case") or {}
    turns = case.get("turns") or []
    n = sum(1 for t in turns if isinstance(t, dict) and t.get("role") == "user")
    if n:
        return n
    msgs = ((detail.get("trace") or {}).get("messages")) or []
    n = sum(1 for m in msgs if isinstance(m, dict) and m.get("role") == "user")
    return n or 1


def case_trace_url(row: CaseResultRow) -> Optional[str]:
    detail = row.detail_json or {}
    url = ((detail.get("trace") or {}).get("langfuse_trace_url"))
    return url if isinstance(url, str) and url else None


def guideline_counts(row: CaseResultRow) -> Optional[tuple[float, float]]:
    detail = row.detail_json or {}
    scores = detail.get("guideline_scores") or []
    applicable = [item for item in scores if item.get("applicable", True)]
    if not applicable:
        return None
    return (
        sum(float(item.get("score", 0)) for item in applicable),
        sum(float(item.get("max_score", 0)) for item in applicable),
    )


def filtered_case_rows(
    session: Session,
    run_id: int,
    *,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    turns: Optional[str] = None,
    guideline: Optional[str] = None,
    load_detail_json: bool = True,
) -> list[CaseResultRow]:
    if turns and not load_detail_json:
        load_detail_json = True
    stmt = select(CaseResultRow).where(CaseResultRow.run_id == run_id)
    if not load_detail_json:
        stmt = stmt.options(load_only(*_LIST_CASE_COLUMNS))
    if level:
        stmt = stmt.where(CaseResultRow.level == level)
    if release_passed is not None:
        stmt = stmt.where(CaseResultRow.release_passed == release_passed)
    if stability:
        stmt = stmt.where(CaseResultRow.stability == stability)
    if scenario:
        stmt = stmt.where(CaseResultRow.scenario == scenario)
    stmt = stmt.order_by(CaseResultRow.sample_id)
    rows = list(session.execute(stmt).scalars().all())
    for r in rows:
        _attach_row_display_fields(r, load_detail_json=load_detail_json)
    if guideline == "full":
        rows = [r for r in rows if r.guideline_max and r.guideline_earned == r.guideline_max]
    elif guideline == "partial":
        rows = [r for r in rows if r.guideline_max and r.guideline_earned != r.guideline_max]
    elif guideline == "none":
        rows = [r for r in rows if not r.guideline_max]
    if turns == "single":
        rows = [r for r in rows if r.n_turns <= 1]
    elif turns == "multi":
        rows = [r for r in rows if r.n_turns > 1]
    return rows


def attach_review_summary(
    session: Session, run_id: int, rows: list[CaseResultRow]
) -> None:
    by_sample: dict[str, list[CaseAnnotation]] = {}
    for a in session.execute(
        select(CaseAnnotation)
        .where(CaseAnnotation.run_id == run_id)
        .order_by(CaseAnnotation.created_at)
    ).scalars().all():
        by_sample.setdefault(a.sample_id, []).append(a)
    for row in rows:
        anns = by_sample.get(row.sample_id)
        if anns:
            latest = anns[-1]
            row.review = ReviewSummary(
                verdict=latest.verdict,
                reviewer=latest.reviewer,
                suggestion=latest.suggestion,
                comment=latest.comment,
                count=len(anns),
            )
        else:
            row.review = None


def case_scores(d: dict[str, Any]) -> CaseScores:
    d = d or {}
    return CaseScores(
        medical_safety_passed=bool(d.get("medical_safety_passed")),
        release_passed=bool(d.get("release_passed")),
        composite_score=d.get("composite_score"),
        grade=d.get("grade") or "",
        dimension_scores=d.get("dimension_scores") or {},
        dimension_max=d.get("dimension_max") or {},
        dimension_raw_scores=d.get("dimension_raw_scores") or {},
        end_scores=d.get("end_scores") or {},
        guideline_scores=d.get("guideline_scores") or [],
        score_deductions=d.get("score_deductions") or [],
        failure_tags=d.get("failure_tags") or [],
        verdicts=[
            {
                "name": v.get("name"),
                "passed": v.get("passed"),
                "score": v.get("score"),
                "max_score": v.get("max_score"),
                "reason": v.get("reason"),
            }
            for v in (d.get("verdicts") or [])
        ],
    )


def override_from_yaml(yaml_text: str, sample_id: str) -> dict[str, Any]:
    try:
        docs = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=422, detail=f"YAML 解析失败：{exc}") from exc
    items = docs if isinstance(docs, list) else [docs]
    for it in items:
        if isinstance(it, dict) and it.get("sample_id") == sample_id:
            return {"sample_id": sample_id, "evaluation": it.get("evaluation") or {}}
    raise HTTPException(status_code=400, detail=f"YAML 中未找到用例 {sample_id}")


def queue_reasons(
    row: CaseResultRow,
    *,
    dispersion_threshold: float = 0.5,
    baseline: CaseResultRow | None = None,
    cross_run_comparable: bool = True,
) -> list[str]:
    reasons: list[str] = []
    if not row.release_passed:
        reasons.append("release_failed")
    if not row.medical_safety_passed:
        reasons.append("medical_safety_failed")
    if baseline is not None and cross_run_comparable:
        from .cross_run_diff import cross_run_diff_reasons

        for tag in cross_run_diff_reasons(row, baseline):
            if tag not in reasons:
                reasons.append(tag)
    return reasons


def case_row_or_404(session: Session, run_id: int, sample_id: str) -> CaseResultRow:
    row = session.execute(
        select(CaseResultRow).where(
            CaseResultRow.run_id == run_id, CaseResultRow.sample_id == sample_id
        )
    ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} 中无用例 {sample_id}")
    return row
