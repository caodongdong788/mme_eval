"""胖产物滚动清理（参见 OpenSpec change persist-traces-rejudge）。

拆「长期可 diff」与「短期可重判」：
  * ``report.json``（瘦底座）永久保留 → 跨版本 diff / 趋势不断链。
  * 胖产物（``traces.jsonl.gz`` / ``transcripts.xlsx`` / 残留 ``traces.partial.jsonl``）
    按 ``keep_last``（按 report.json mtime 保留最近 N 个）与可选 ``ttl_days`` 滚动清理。
  * 含 ``KEEP`` sentinel 文件的 run 目录在 ``keep_tagged=true`` 时永久豁免。

效果：稳态磁盘 ≈ keep_last × 单 run 压缩后大小，不随评测次数线性爆炸。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from .trace_store import PARTIAL, TRACES_GZ

__all__ = ["FAT_ARTIFACTS", "KEEP_SENTINEL", "REPORT_JSON", "PruneResult", "prune_outputs"]

# 胖产物文件名（被 retention 清理；report.json 永不在列）
FAT_ARTIFACTS = (TRACES_GZ, PARTIAL, "transcripts.xlsx")
KEEP_SENTINEL = "KEEP"
REPORT_JSON = "report.json"


@dataclass
class PruneResult:
    pruned_runs: list[str] = field(default_factory=list)  # 被清理胖产物的 run 目录名
    removed_files: list[Path] = field(default_factory=list)  # 被删（或 dry-run 待删）的文件
    kept_runs: list[str] = field(default_factory=list)  # 保留胖产物的 run 目录名（含豁免）


def _run_dirs(outputs_dir: Path) -> list[Path]:
    """所有含 report.json 的 run 目录，按 report.json mtime 降序（最新在前）。"""
    if not outputs_dir.is_dir():
        return []
    dirs = [d for d in outputs_dir.iterdir() if d.is_dir() and (d / REPORT_JSON).is_file()]
    dirs.sort(key=lambda d: (d / REPORT_JSON).stat().st_mtime, reverse=True)
    return dirs


def prune_outputs(
    outputs_dir: Path,
    *,
    keep_last: int = 20,
    ttl_days: int | None = None,
    keep_tagged: bool = True,
    dry_run: bool = False,
) -> PruneResult:
    """清理 ``outputs_dir`` 下历史 run 的胖产物。

    某 run 的胖产物会被清理，当且仅当：
      * （``keep_last>0`` 时）它不在最近 ``keep_last`` 个 run 内，**或**
      * （``ttl_days`` 给定时）它的 report.json 早于 now - ttl_days。
    且不满足豁免（``keep_tagged`` 且目录含 ``KEEP``）。``report.json`` 始终保留。
    """
    outputs_dir = Path(outputs_dir)
    result = PruneResult()
    dirs = _run_dirs(outputs_dir)
    now = time.time()
    ttl_cutoff = (now - ttl_days * 86400) if ttl_days else None

    for idx, d in enumerate(dirs):
        exempt_tagged = keep_tagged and (d / KEEP_SENTINEL).exists()
        over_keep_last = keep_last > 0 and idx >= keep_last
        over_ttl = ttl_cutoff is not None and (d / REPORT_JSON).stat().st_mtime < ttl_cutoff
        should_prune = (over_keep_last or over_ttl) and not exempt_tagged

        if not should_prune:
            result.kept_runs.append(d.name)
            continue

        removed_any = False
        for fname in FAT_ARTIFACTS:
            f = d / fname
            if f.exists():
                result.removed_files.append(f)
                removed_any = True
                if not dry_run:
                    f.unlink(missing_ok=True)
        if removed_any:
            result.pruned_runs.append(d.name)
        else:
            result.kept_runs.append(d.name)

    return result
