"""JSON 形式的全量报告 —— 用于版本 diff 与人审界面。"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import RunReport


def write_json(report: RunReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path
