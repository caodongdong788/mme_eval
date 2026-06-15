"""用例结果查询、派生展示字段与 HITL 队列辅助。"""

from __future__ import annotations

from typing import Any, Optional

import yaml
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_db import CaseAnnotation, CaseResultRow
from ..schemas import CaseScores, ReviewSummary


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


def guideline_counts(row: CaseResultRow) -> Optional[tuple[int, int]]:
    detail = row.detail_json or {}
    points = (detail.get("case") or {}).get("scoring_points") or []
    anchored = [
        i for i, sp in enumerate(points) if isinstance(sp, dict) and sp.get("guideline")
    ]
    if not anchored:
        return None
    passed_by_idx: dict[int, bool] = {}
    prefix = "scoring_point.point"
    for v in detail.get("verdicts") or []:
        name = v.get("name", "") if isinstance(v, dict) else ""
        if name.startswith(prefix):
            try:
                idx = int(name[len(prefix) :])
            except ValueError:
                continue
            passed_by_idx[idx] = bool(v.get("passed"))
    matched = sum(1 for i in anchored if passed_by_idx.get(i, False))
    return matched, len(anchored)


def filtered_case_rows(
    session: Session,
    run_id: int,
    *,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    score_profile: Optional[str] = None,
    turns: Optional[str] = None,
    guideline: Optional[str] = None,
) -> list[CaseResultRow]:
    stmt = select(CaseResultRow).where(CaseResultRow.run_id == run_id)
    if level:
        stmt = stmt.where(CaseResultRow.level == level)
    if release_passed is not None:
        stmt = stmt.where(CaseResultRow.release_passed == release_passed)
    if stability:
        stmt = stmt.where(CaseResultRow.stability == stability)
    if scenario:
        stmt = stmt.where(CaseResultRow.scenario == scenario)
    if guideline == "full":
        stmt = stmt.where(CaseResultRow.guideline_match_rate >= 0.999)
    elif guideline == "partial":
        stmt = stmt.where(
            CaseResultRow.guideline_match_rate.is_not(None),
            CaseResultRow.guideline_match_rate < 0.999,
        )
    elif guideline == "none":
        stmt = stmt.where(CaseResultRow.guideline_match_rate.is_(None))
    stmt = stmt.order_by(CaseResultRow.sample_id)
    rows = list(session.execute(stmt).scalars().all())
    if score_profile:
        rows = [r for r in rows if r.score_profile == score_profile]
    for r in rows:
        r.n_turns = case_n_turns(r)
        r.langfuse_trace_url = case_trace_url(r)
        gc = guideline_counts(r)
        r.guideline_matched = gc[0] if gc else None
        r.guideline_total = gc[1] if gc else None
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
        hard_gate_passed=bool(d.get("hard_gate_passed")),
        gate_passed=bool(d.get("gate_passed")),
        release_passed=bool(d.get("release_passed")),
        composite_score=d.get("composite_score"),
        grade=d.get("grade") or "",
        dimension_scores=d.get("dimension_scores") or {},
        dimension_max=d.get("dimension_max") or {},
        score_profile=d.get("score_profile") or "",
        score_deductions=d.get("score_deductions") or [],
        failure_tags=d.get("failure_tags") or [],
        needs_human_review=bool(d.get("needs_human_review")),
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
            ov: dict[str, Any] = {"sample_id": sample_id}
            for f in ("expected_behavior", "hard_gates", "rubric", "scoring_points"):
                if it.get(f) is not None:
                    ov[f] = it[f]
            return ov
    raise HTTPException(status_code=400, detail=f"YAML 中未找到用例 {sample_id}")


def is_red_flag(row: CaseResultRow) -> bool:
    triage = (
        ((row.detail_json or {}).get("case") or {}).get("hard_gates") or {}
    ).get("red_flag_triage")
    return bool(triage) and triage != "none"


def queue_reasons(row: CaseResultRow) -> list[str]:
    reasons: list[str] = []
    if row.needs_human_review:
        reasons.append("needs_human_review")
    if not row.release_passed:
        reasons.append("release_failed")
        if is_red_flag(row):
            reasons.append("red_flag_failed")
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
