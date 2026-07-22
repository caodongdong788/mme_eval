"""评测产物落库、双写 outputs 与存储治理。"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from medeval.config import Config
from medeval.models import RunReport
from medeval.service import write_core_artifacts

from ..db import session_scope
from ..ingest import finalize_run
from ..models_db import EvalRun
from ..paths import safe_join
from ..settings import Settings

logger = logging.getLogger(__name__)

PLAN = "plan.json"
CASE_IMAGES_DIR = "case-images"
_MARKDOWN_IMAGE_PATH_RE = re.compile(r"!\[[^\]]*\]\(\s*(images/[^\s)]+)", re.IGNORECASE)


def write_run_plan(out_dir: Path, cases: list[Any], n_runs: int) -> None:
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / PLAN).write_text(
            json.dumps(
                {"sample_ids": [c.sample_id for c in cases], "n_runs": int(n_runs)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001
        logger.debug("写入 run plan 失败（%s）", out_dir, exc_info=True)


def snapshot_case_images(out_dir: Path, cases: list[Any], benchmark_root: Path) -> None:
    """冻结本次评测实际引用的图片，避免 benchmark 后续更新影响明细预览。"""
    snapshot_root = out_dir / CASE_IMAGES_DIR
    try:
        for case in cases:
            for turn in getattr(case, "turns", []):
                declared = list(getattr(turn, "images", []) or [])
                content = getattr(turn, "content", "")
                if isinstance(content, str):
                    declared.extend(_MARKDOWN_IMAGE_PATH_RE.findall(content))
                for image_path in dict.fromkeys(declared):
                    if not isinstance(image_path, str):
                        continue
                    source = safe_join(benchmark_root, image_path)
                    if not source.is_file():
                        raise FileNotFoundError(f"评测图片不存在：{image_path}")
                    target = safe_join(snapshot_root, image_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    except Exception:
        shutil.rmtree(snapshot_root, ignore_errors=True)
        raise


def copy_case_image_snapshot(source_dir: Path, out_dir: Path) -> None:
    """派生 Run 复用源 Run 已冻结的图片快照。"""
    source = source_dir / CASE_IMAGES_DIR
    if not source.is_dir():
        return
    destination = out_dir / CASE_IMAGES_DIR
    shutil.copytree(source, destination, dirs_exist_ok=True)


def read_run_plan(out_dir: Path) -> dict[str, Any] | None:
    try:
        p = out_dir / PLAN
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        logger.debug("读取 run plan 失败（%s）", out_dir, exc_info=True)
        return None
    return None


def persist_outcome(
    run_id: int,
    report: RunReport,
    out_dir: Path,
    *,
    prev_json: Path | None,
    parent_run_id: int | None = None,
) -> None:
    has_traces = (out_dir / "traces.jsonl.gz").is_file()
    with session_scope() as session:
        row = session.get(EvalRun, run_id)
        finalize_run(session, row, report)
        row.has_traces = has_traces
        if parent_run_id is not None:
            row.parent_run_id = parent_run_id
        if prev_json is not None:
            from .cross_run_diff import run_id_from_prev_json

            against_id = run_id_from_prev_json(session, prev_json)
            if against_id is not None and against_id != run_id:
                row.diff_against_run_id = against_id

    try:
        write_core_artifacts(report, out_dir, prev_json=prev_json)
    except Exception:  # noqa: BLE001
        logger.warning("run %s 写 outputs 产物失败（不影响落库）", run_id, exc_info=True)


def apply_retention(config: Config, settings: Settings) -> None:
    from .. import eval_job as ej

    ret = config.run.retention
    if not getattr(ret, "enabled", True):
        return
    try:
        ej.retention.prune_outputs(
            settings.outputs_dir,
            keep_last=ret.keep_last,
            ttl_days=ret.ttl_days,
            keep_tagged=ret.keep_tagged,
        )
    except Exception:  # noqa: BLE001
        logger.warning("retention 清理历史产物失败（不影响评测）", exc_info=True)
