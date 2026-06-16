"""跨版本大 diff 自动入 HITL（change cross-run-diff-hitl）。"""

from __future__ import annotations

from server.db import session_scope
from server.models_db import CaseResultRow, EvalRun
from server.services.cross_run_diff import cross_run_diff_reasons, runs_comparable
from server.services.review import get_review_queue


def _case_row(
    run_id: int,
    sample_id: str,
    *,
    release_passed: bool = True,
    hard_gate_passed: bool = True,
    gate_passed: bool = True,
    composite_score: float = 0.9,
    detail_json: dict | None = None,
) -> CaseResultRow:
    return CaseResultRow(
        run_id=run_id,
        sample_id=sample_id,
        scenario="x",
        level="L2",
        release_passed=release_passed,
        hard_gate_passed=hard_gate_passed,
        gate_passed=gate_passed,
        composite_score=composite_score,
        detail_json=detail_json or {},
    )


def test_cross_run_diff_score_swing():
    cur = _case_row(2, "a", composite_score=0.60)
    base = _case_row(1, "a", composite_score=0.92)
    assert "cross_run_diff" in cross_run_diff_reasons(cur, base)


def test_cross_run_diff_gate_flip():
    cur = _case_row(2, "a", hard_gate_passed=False)
    base = _case_row(1, "a", hard_gate_passed=True)
    assert "cross_run_diff" in cross_run_diff_reasons(cur, base)


def test_cross_run_diff_dimension_swing():
    cur = _case_row(
        2,
        "a",
        detail_json={"dimension_scores": {"function": 0.10}},
    )
    base = _case_row(
        1,
        "a",
        detail_json={"dimension_scores": {"function": 0.35}},
    )
    assert "cross_run_diff" in cross_run_diff_reasons(cur, base)


def test_cross_run_diff_no_op_when_stable():
    cur = _case_row(2, "a", composite_score=0.88)
    base = _case_row(1, "a", composite_score=0.90)
    assert cross_run_diff_reasons(cur, base) == []


def test_runs_comparable_requires_same_fingerprints():
    a = EvalRun(judge_fingerprints={"rule": "x"})
    b = EvalRun(judge_fingerprints={"rule": "y"})
    assert runs_comparable(a, b) is False


def test_review_queue_includes_cross_run_diff(client, settings):
    with session_scope() as s:
        base = EvalRun(
            run_slug="base_cr",
            name="base",
            status="success",
            benchmark_id=1,
            judge_fingerprints={"rule": "fp1"},
        )
        cur = EvalRun(
            run_slug="cur_cr",
            name="cur",
            status="success",
            benchmark_id=1,
            judge_fingerprints={"rule": "fp1"},
            diff_against_run_id=None,
        )
        s.add(base)
        s.add(cur)
        s.flush()
        cur.diff_against_run_id = base.id
        s.flush()
        s.add(_case_row(base.id, "swing", composite_score=0.95))
        s.add(_case_row(cur.id, "swing", composite_score=0.65))
        s.add(_case_row(base.id, "ok", composite_score=0.90))
        s.add(_case_row(cur.id, "ok", composite_score=0.88))
        rid = cur.id

    items = {it["sample_id"]: it for it in client.get(f"/api/runs/{rid}/review-queue").json()}
    assert "swing" in items
    assert "cross_run_diff" in items["swing"]["reasons"]
    assert "ok" not in items
