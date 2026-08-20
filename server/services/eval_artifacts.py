"""评测产物落库、双写 outputs 与存储治理。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from copy import deepcopy
from datetime import datetime
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import select

from medeval.config import Config
from medeval.models import CaseResult, RunReport
from medeval.reporter.aggregator import build_report
from medeval.service import write_core_artifacts

from ..db import session_scope
from ..ingest import attach_case_results, finalize_run, populate_run_summary
from ..models_db import CaseResultRow, EvalRun
from ..paths import safe_join
from ..settings import Settings

logger = logging.getLogger(__name__)

PLAN = "plan.json"
CASE_IMAGES_DIR = "case-images"
_MARKDOWN_IMAGE_PATH_RE = re.compile(r"!\[[^\]]*\]\(\s*(images/[^\s)]+)", re.IGNORECASE)


def persist_incremental_report(run_id: int, report: RunReport) -> None:
    """写入阶段性汇总与已完成明细，但不提前结束运行状态。"""
    with session_scope() as session:
        row = session.get(EvalRun, run_id)
        if row is None:
            raise ValueError(f"run {run_id} 不存在")
        status = row.status
        error_msg = row.error_msg
        started_at = row.started_at
        finished_at = row.finished_at
        populate_run_summary(row, report)
        attach_case_results(session, run_id, report)
        row.status = status
        row.error_msg = error_msg
        row.started_at = started_at or report.started_at
        row.finished_at = finished_at


def load_persisted_case_results(
    run_id: int, sample_ids: Iterable[str]
) -> dict[str, CaseResult]:
    """读取当前 run 已完整落库的 CaseResult，供原地断点续跑复用。"""
    allowed = set(sample_ids)
    if not allowed:
        return {}
    restored: dict[str, CaseResult] = {}
    with session_scope() as session:
        rows = session.scalars(
            select(CaseResultRow)
            .where(
                CaseResultRow.run_id == run_id,
                CaseResultRow.sample_id.in_(allowed),
            )
            .order_by(CaseResultRow.id)
        )
        for row in rows:
            try:
                result = CaseResult.model_validate(row.detail_json)
            except Exception:  # noqa: BLE001 - 旧/损坏明细不能阻断其余 Case 续跑
                logger.warning(
                    "run %s 的已落库 Case %s 无法恢复，将重新判分",
                    run_id,
                    row.sample_id,
                    exc_info=True,
                )
                continue
            if result.case.sample_id != row.sample_id:
                logger.warning(
                    "run %s 的 Case %s 明细 sample_id 不一致，将重新判分",
                    run_id,
                    row.sample_id,
                )
                continue
            restored[row.sample_id] = result
    return restored


class IncrementalRunPersister:
    """把并发完成的 Case 串行聚合并幂等落库。"""

    def __init__(
        self,
        run_id: int,
        *,
        run_name: str,
        adapter_type: str,
        config_snapshot: dict[str, Any],
        description: str,
        n_runs: int,
        sample_order: list[str],
        initial_results: Iterable[CaseResult] = (),
        on_case_persisted: Callable[[CaseResult], Awaitable[None]] | None = None,
    ) -> None:
        self.run_id = run_id
        self.run_name = run_name
        self.adapter_type = adapter_type
        self.config_snapshot = deepcopy(config_snapshot)
        self.description = description
        self.n_runs = n_runs
        self._sample_order = {
            sample_id: index for index, sample_id in enumerate(sample_order)
        }
        self._results: dict[str, CaseResult] = {
            result.case.sample_id: result
            for result in initial_results
            if result.case.sample_id in self._sample_order
        }
        self._started_at = datetime.utcnow()
        self._lock = asyncio.Lock()
        self._on_case_persisted = on_case_persisted

    async def __call__(self, result: CaseResult) -> None:
        async with self._lock:
            self._results[result.case.sample_id] = result
            completed = sorted(
                self._results.values(),
                key=lambda item: self._sample_order.get(
                    item.case.sample_id, len(self._sample_order)
                ),
            )
            partial = build_report(
                run_name=self.run_name,
                results=completed,
                adapter_type=self.adapter_type,
                config_snapshot=deepcopy(self.config_snapshot),
                description=self.description,
                started_at=self._started_at,
                n_runs=self.n_runs,
            )
            persist_incremental_report(self.run_id, partial)
        # 必须在阶段性结果提交后通知后续流水线，确保归因读取到完整冻结明细；
        # 通知放在持久化锁外，避免归因入队短暂波动阻塞其他 Case 落库。
        if self._on_case_persisted is not None:
            await self._on_case_persisted(result)


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
