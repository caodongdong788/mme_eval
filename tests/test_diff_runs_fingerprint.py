"""diff_runs 的 fingerprint 警告路径。"""

from __future__ import annotations

import json
from pathlib import Path

from medeval.reporter.diff import _fingerprint_warning, diff_runs


def _minimal_report(fps: dict[str, str] | None) -> dict:
    """构造一份最小可 diff 的 report dict。"""
    r: dict = {
        "total": 1,
        "passed": 1,
        "by_level": {},
        "results": [
            {
                "case": {"sample_id": "demo"},
                "release_passed": True,
            }
        ],
    }
    if fps is not None:
        r["judge_fingerprints"] = fps
    return r


def test_warning_omitted_when_both_empty():
    assert _fingerprint_warning(_minimal_report({}), _minimal_report({})) == ""


def test_warning_when_prev_missing_field():
    cur = _minimal_report({"hard_gate": "abc123", "rule": "def456"})
    prev = _minimal_report(None)
    w = _fingerprint_warning(cur, prev)
    assert "ℹ️" in w
    assert "abc123" in w
    assert "def456" in w


def test_warning_when_fp_differs():
    cur = _minimal_report({"hard_gate": "NEW000", "rule": "same111"})
    prev = _minimal_report({"hard_gate": "OLD000", "rule": "same111"})
    w = _fingerprint_warning(cur, prev)
    assert "⚠️" in w
    assert "hard_gate" in w
    assert "OLD000" in w
    assert "NEW000" in w
    # 同值的 judge 不应出现在表里
    rule_table_rows = [line for line in w.splitlines() if line.startswith("| `rule`")]
    assert rule_table_rows == []


def test_warning_silent_when_all_equal():
    cur = _minimal_report({"hard_gate": "abc", "rule": "def"})
    prev = _minimal_report({"hard_gate": "abc", "rule": "def"})
    assert _fingerprint_warning(cur, prev) == ""


def test_diff_runs_inserts_warning_at_top(tmp_path: Path):
    cur_path = tmp_path / "cur.json"
    prev_path = tmp_path / "prev.json"
    cur_path.write_text(
        json.dumps(_minimal_report({"hard_gate": "NEW000"})), encoding="utf-8"
    )
    prev_path.write_text(
        json.dumps(_minimal_report({"hard_gate": "OLD000"})), encoding="utf-8"
    )
    md = diff_runs(cur_path, prev_path)
    # 警告必须出现在最早，且早于 "总通过率"
    warn_idx = md.find("⚠️")
    rate_idx = md.find("总通过率")
    assert 0 <= warn_idx < rate_idx, f"warn={warn_idx}, rate={rate_idx}: {md}"
