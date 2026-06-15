"""diff_runs 的性能（会话延迟）对比块。"""

from __future__ import annotations

import json
from pathlib import Path

from medeval.reporter.diff import _latency_diff, diff_runs


def _report(latency: dict | None) -> dict:
    r: dict = {
        "total": 1,
        "passed": 1,
        "by_level": {},
        "results": [{"case": {"sample_id": "demo"}, "release_passed": True}],
    }
    if latency is not None:
        r["latency_summary"] = latency
    return r


_CUR = {"count": 2, "avg_ms": 6000.0, "median_ms": 5800.0, "p90_ms": 7000.0, "max_ms": 7200.0}
_PREV = {"count": 2, "avg_ms": 5000.0, "median_ms": 5000.0, "p90_ms": 6000.0, "max_ms": 6000.0}


def test_latency_diff_both_present():
    out = _latency_diff(_report(_CUR), _report(_PREV))
    assert "性能变化" in out
    assert "仅记录" in out
    # 四项指标都在
    for label in ("平均", "中位", "P90", "最大"):
        assert label in out
    # 平均 6000 vs 5000 → +1000，变慢
    assert "6000" in out and "5000" in out
    assert "+1000" in out
    assert "↑" in out  # 变慢方向
    assert "20.0%" in out  # +1000/5000


def test_latency_diff_faster_marks_down_arrow():
    # 当前比上版更快
    out = _latency_diff(_report(_PREV), _report(_CUR))
    assert "↓" in out
    assert "-1000" in out


def test_latency_diff_prev_missing_is_info_not_crash():
    out = _latency_diff(_report(_CUR), _report(None))
    assert "ℹ️" in out
    assert "上版本" in out
    assert "性能" in out


def test_latency_diff_cur_missing_returns_empty():
    assert _latency_diff(_report(None), _report(_PREV)) == ""


def test_diff_runs_appends_latency_block(tmp_path: Path):
    cur_path = tmp_path / "cur.json"
    prev_path = tmp_path / "prev.json"
    cur_path.write_text(json.dumps(_report(_CUR)), encoding="utf-8")
    prev_path.write_text(json.dumps(_report(_PREV)), encoding="utf-8")
    md = diff_runs(cur_path, prev_path)
    assert "性能变化" in md
    # 性能块出现在通过率之后（位于对比段末尾）
    assert md.find("总通过率") < md.find("性能变化")
