"""跨版本 run 对比 → HITL 入队原因（平台侧，不改判分内核）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_db import CaseResultRow, EvalRun

COMPOSITE_SWING_THRESHOLD = 0.25
DIMENSION_SWING_THRESHOLD = 0.15


def runs_comparable(current: EvalRun, baseline: EvalRun) -> bool:
    """判分尺子可比：同 benchmark 且 judge_fingerprints 一致。"""
    if (current.benchmark_id or None) != (baseline.benchmark_id or None):
        return False
    return (current.judge_fingerprints or {}) == (baseline.judge_fingerprints or {})


def cross_run_diff_reasons(
    current: CaseResultRow,
    baseline: CaseResultRow,
    *,
    composite_threshold: float = COMPOSITE_SWING_THRESHOLD,
    dimension_threshold: float = DIMENSION_SWING_THRESHOLD,
) -> list[str]:
    """相对基线 case 的剧烈变化；无变化返回空列表。"""
    if _gate_flipped(current, baseline):
        return ["cross_run_diff"]
    if _composite_swing(current, baseline, composite_threshold):
        return ["cross_run_diff"]
    if _dimension_swing(current, baseline, dimension_threshold):
        return ["cross_run_diff"]
    return []


def _gate_flipped(current: CaseResultRow, baseline: CaseResultRow) -> bool:
    return (
        current.release_passed != baseline.release_passed
        or current.hard_gate_passed != baseline.hard_gate_passed
        or current.gate_passed != baseline.gate_passed
    )


def _composite_swing(
    current: CaseResultRow,
    baseline: CaseResultRow,
    threshold: float,
) -> bool:
    cur = current.composite_score
    base = baseline.composite_score
    if cur is None or base is None:
        return False
    return abs(cur - base) >= threshold


def _dimension_swing(
    current: CaseResultRow,
    baseline: CaseResultRow,
    threshold: float,
) -> bool:
    cur_dims = ((current.detail_json or {}).get("dimension_scores")) or {}
    base_dims = ((baseline.detail_json or {}).get("dimension_scores")) or {}
    if not isinstance(cur_dims, dict) or not isinstance(base_dims, dict):
        return False
    for key in set(cur_dims) | set(base_dims):
        cv, bv = cur_dims.get(key), base_dims.get(key)
        if cv is None or bv is None:
            continue
        if abs(float(cv) - float(bv)) >= threshold:
            return True
    return False


def resolve_baseline_run(session: Session, run: EvalRun) -> EvalRun | None:
    """解析可比基线 run：优先 diff_against_run_id，否则同 benchmark 上一成功 run。"""
    if run.diff_against_run_id is not None:
        baseline = session.get(EvalRun, run.diff_against_run_id)
        if baseline is not None and baseline.status == "success":
            return baseline
    if run.benchmark_id is None:
        return None
    candidates = session.execute(
        select(EvalRun)
        .where(
            EvalRun.status == "success",
            EvalRun.benchmark_id == run.benchmark_id,
            EvalRun.id < run.id,
        )
        .order_by(EvalRun.id.desc())
    ).scalars()
    for candidate in candidates:
        if runs_comparable(run, candidate):
            return candidate
    return None


def baseline_case_map(session: Session, run: EvalRun) -> dict[str, CaseResultRow]:
    """基线 run 的 sample_id → case 行；不可比或缺失时返回空 dict。"""
    baseline = resolve_baseline_run(session, run)
    if baseline is None or not runs_comparable(run, baseline):
        return {}
    rows = session.execute(
        select(CaseResultRow).where(CaseResultRow.run_id == baseline.id)
    ).scalars().all()
    return {r.sample_id: r for r in rows}


def run_id_from_prev_json(session: Session, prev_json) -> int | None:
    """从 outputs 上一版 report.json 路径反查 eval_run.id。"""
    from pathlib import Path

    path = Path(prev_json)
    slug = path.parent.name
    return session.execute(
        select(EvalRun.id).where(EvalRun.run_slug == slug)
    ).scalar_one_or_none()
