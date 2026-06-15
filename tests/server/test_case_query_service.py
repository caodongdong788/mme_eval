"""server.services.case_query 纯函数单测（P0 迁出 _helpers）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from server.services.case_query import (
    case_n_turns,
    case_scores,
    is_red_flag,
    queue_reasons,
)


def _row(**kwargs):
    defaults = {"needs_human_review": False, "release_passed": True, "detail_json": {}}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_case_scores_maps_detail_fields():
    d = {
        "hard_gate_passed": True,
        "gate_passed": True,
        "release_passed": False,
        "composite_score": 0.72,
        "grade": "良好",
        "dimension_scores": {"safety": 0.3},
        "dimension_max": {"safety": 0.3},
        "score_profile": "default",
        "score_deductions": ["x"],
        "failure_tags": ["tag_a"],
        "needs_human_review": True,
        "verdicts": [{"name": "rule.foo", "passed": False, "reason": "r"}],
    }
    s = case_scores(d)
    assert s.release_passed is False
    assert s.composite_score == pytest.approx(0.72)
    assert s.verdicts[0]["name"] == "rule.foo"


def test_case_n_turns_from_case_turns():
    row = _row(
        detail_json={
            "case": {"turns": [{"role": "user"}, {"role": "assistant"}, {"role": "user"}]},
            "trace": {"messages": []},
        }
    )
    assert case_n_turns(row) == 2


def test_case_n_turns_fallback_trace_messages():
    row = _row(
        detail_json={
            "case": {},
            "trace": {"messages": [{"role": "user"}]},
        }
    )
    assert case_n_turns(row) == 1


def test_is_red_flag_and_queue_reasons():
    row = _row(
        needs_human_review=True,
        release_passed=False,
        detail_json={"case": {"hard_gates": {"red_flag_triage": "emergency"}}},
    )
    assert is_red_flag(row) is True
    reasons = queue_reasons(row)
    assert "needs_human_review" in reasons
    assert "release_failed" in reasons
    assert "red_flag_failed" in reasons