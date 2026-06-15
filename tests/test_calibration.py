"""人审校准度量脚本单测（change adopt-clinical-benchmark-methodology 阶段5）。

仅度量、不进 CI gate；测纯函数 spearman / pass_agreement / compute_agreement。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "calibration_compute_agreement", _ROOT / "scripts" / "compute_agreement.py"
)
cal = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cal)  # type: ignore[union-attr]


def test_spearman_perfect_monotonic():
    assert cal.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)


def test_spearman_perfect_inverse():
    assert cal.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_spearman_handles_ties_and_degenerate():
    assert cal.spearman([1], [1]) is None          # n<2
    assert cal.spearman([5, 5, 5], [1, 2, 3]) is None  # 一侧方差 0


def test_pass_agreement():
    assert cal.pass_agreement([(True, True), (False, False), (True, False)]) == pytest.approx(2 / 3)
    assert cal.pass_agreement([]) is None


def test_compute_agreement_aligns_by_sample_id():
    human = [
        {"sample_id": "a", "expert_score": 90, "expert_pass": True},
        {"sample_id": "b", "expert_score": 70, "expert_pass": False},
        {"sample_id": "c", "expert_score": 80, "expert_pass": True},
        {"sample_id": "missing", "expert_score": 50, "expert_pass": False},
    ]
    report = {
        "results": [
            {"case": {"sample_id": "a"}, "composite_score": 0.95, "release_passed": True},
            {"case": {"sample_id": "b"}, "composite_score": 0.60, "release_passed": False},
            {"case": {"sample_id": "c"}, "composite_score": 0.85, "release_passed": False},
        ]
    }
    m = cal.compute_agreement(human, report)
    assert m["matched"] == 3
    assert m["unmatched"] == ["missing"]
    # a,b 一致，c 不一致 → 2/3
    assert m["pass_agreement"] == pytest.approx(2 / 3)
    # 人审与自动分排序一致（90>80>70 对 0.95>0.85>0.60）→ ρ=1
    assert m["spearman"] == pytest.approx(1.0)
