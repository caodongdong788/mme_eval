"""历史导入工具：扫描 outputs/*/report.json 落库。

用法：
    python -m server.import_history [outputs_dir]

幂等：已存在同 run_slug 的记录则跳过。导入的 run 不关联 benchmark（benchmark_id=None）。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

from sqlalchemy import select

from medeval.models import RunReport

from .db import init_db, session_scope
from .ingest import ingest_report
from .models_db import EvalRun
from .settings import get_settings


def import_report_file(session, path: Path) -> str:
    """导入单个 report.json；返回 imported / skipped / error。"""
    try:
        report = RunReport.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.error("导入 %s 失败：%s", path, exc)
        return "error"

    existing = session.execute(
        select(EvalRun.id).where(EvalRun.run_slug == report.run_name)
    ).first()
    if existing is not None:
        return "skipped"

    ingest_report(session, report)
    return "imported"


def import_outputs(outputs_dir: Path) -> dict[str, int]:
    counts = {"imported": 0, "skipped": 0, "error": 0}
    files = sorted(outputs_dir.glob("*/report.json"))
    for path in files:
        with session_scope() as session:
            counts[import_report_file(session, path)] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    settings = get_settings()
    outputs_dir = Path(argv[0]) if argv else settings.outputs_dir
    init_db(settings)
    if not outputs_dir.is_dir():
        print(f"目录不存在：{outputs_dir}")
        return 1
    counts = import_outputs(outputs_dir)
    print(
        f"导入完成：新增 {counts['imported']}，跳过 {counts['skipped']}，失败 {counts['error']}"
        f"（来源 {outputs_dir}）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
