"""存储治理 retention/prune 单测（change 2026-06-04-persist-traces-rejudge）。

覆盖：
  - keep_last：超额 run 删胖产物、保 report.json
  - KEEP sentinel：豁免
  - dry_run：只预览不删
  - ttl_days：过期清理
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from medeval import retention


def _make_run(outputs: Path, name: str, *, fat=True, mtime: float | None = None) -> Path:
    d = outputs / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.json").write_text("{}", encoding="utf-8")
    if fat:
        (d / "traces.jsonl.gz").write_bytes(b"x")
        (d / "transcripts.xlsx").write_bytes(b"x")
    if mtime is not None:
        os.utime(d / "report.json", (mtime, mtime))
    return d


def test_keep_last_prunes_fat_keeps_report(tmp_path: Path):
    outputs = tmp_path / "outputs"
    base = time.time()
    # 3 个 run，mtime 递增（r3 最新）
    for i, name in enumerate(["r1", "r2", "r3"]):
        _make_run(outputs, name, mtime=base + i)

    result = retention.prune_outputs(outputs, keep_last=2, ttl_days=None, keep_tagged=True)
    # 最旧的 r1 胖产物被删
    assert not (outputs / "r1" / "traces.jsonl.gz").exists()
    assert not (outputs / "r1" / "transcripts.xlsx").exists()
    # report.json 永远保留
    assert (outputs / "r1" / "report.json").exists()
    # 最近 2 个保留胖产物
    assert (outputs / "r3" / "traces.jsonl.gz").exists()
    assert (outputs / "r2" / "traces.jsonl.gz").exists()
    assert "r1" in result.pruned_runs


def test_keep_sentinel_exempts(tmp_path: Path):
    outputs = tmp_path / "outputs"
    base = time.time()
    _make_run(outputs, "r1", mtime=base)
    _make_run(outputs, "r2", mtime=base + 1)
    _make_run(outputs, "r3", mtime=base + 2)
    (outputs / "r1" / retention.KEEP_SENTINEL).write_text("")

    retention.prune_outputs(outputs, keep_last=1, ttl_days=None, keep_tagged=True)
    # r1 有 KEEP → 即便超额也保留胖产物
    assert (outputs / "r1" / "traces.jsonl.gz").exists()
    # r2 超额无豁免 → 删
    assert not (outputs / "r2" / "traces.jsonl.gz").exists()


def test_dry_run_does_not_delete(tmp_path: Path):
    outputs = tmp_path / "outputs"
    base = time.time()
    _make_run(outputs, "r1", mtime=base)
    _make_run(outputs, "r2", mtime=base + 1)
    result = retention.prune_outputs(outputs, keep_last=1, ttl_days=None, dry_run=True)
    # 文件仍在
    assert (outputs / "r1" / "traces.jsonl.gz").exists()
    # 但报告里列出了将清理对象
    assert result.removed_files  # 预览非空


def test_keep_last_zero_keeps_all(tmp_path: Path):
    outputs = tmp_path / "outputs"
    base = time.time()
    _make_run(outputs, "r1", mtime=base)
    _make_run(outputs, "r2", mtime=base + 1)
    retention.prune_outputs(outputs, keep_last=0, ttl_days=None)
    assert (outputs / "r1" / "traces.jsonl.gz").exists()
    assert (outputs / "r2" / "traces.jsonl.gz").exists()


def test_ttl_days_prunes_old(tmp_path: Path):
    outputs = tmp_path / "outputs"
    now = time.time()
    _make_run(outputs, "old", mtime=now - 10 * 86400)
    _make_run(outputs, "fresh", mtime=now)
    retention.prune_outputs(outputs, keep_last=0, ttl_days=7)
    assert not (outputs / "old" / "traces.jsonl.gz").exists()
    assert (outputs / "fresh" / "traces.jsonl.gz").exists()
    assert (outputs / "old" / "report.json").exists()
