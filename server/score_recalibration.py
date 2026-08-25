"""发布后重算尚未升级的历史 Agent 评测八维得分。

护士端由归一化 15 分改为原始 10 分后，既有 CaseResult 仍保存旧口径。
本模块只读取已落库的 CaseResult 判分原始数据并重新聚合，不会调用 cx-agent、
Judge、RAG 或任何外部服务。发布脚本每次均可调用；每个 Run 保存的评分版本保证
幂等，并允许中断后从尚未完成的 Run 继续。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from medeval.models import CaseResult
from medeval.reporter.aggregator import build_report

from .db import init_db, session_scope
from .ingest import build_case_row, populate_run_summary, update_case_row
from .models_db import CaseResultRow, EvalRun
from .settings import Settings, get_settings


SCORE_SCHEMA_VERSION = "nurse-raw-10-v1"
_FINAL_RUN_STATUSES = ("success", "failed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _snapshot(run: EvalRun) -> dict[str, Any]:
    return dict(run.config_snapshot) if isinstance(run.config_snapshot, dict) else {}


def _candidate_run_ids() -> list[int]:
    """返回有已保存结果、但尚未按新口径重算的 Agent 八维 Run。"""
    with session_scope() as session:
        rows = session.execute(
            select(EvalRun.id, EvalRun.config_snapshot)
            .join(CaseResultRow, CaseResultRow.run_id == EvalRun.id)
            .where(
                EvalRun.status.in_(_FINAL_RUN_STATUSES),
                EvalRun.scoring_standard == "cx_eight_dimension",
            )
            .distinct()
            .order_by(EvalRun.id)
        ).all()
    return [
        int(run_id)
        for run_id, snapshot in rows
        if not isinstance(snapshot, dict)
        or snapshot.get("score_schema_version") != SCORE_SCHEMA_VERSION
    ]


def _recalculate_run(run_id: int) -> int:
    """在一个短事务内重算一个 Run；返回重写的 Case 数。"""
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        if run is None:
            return 0
        snapshot = _snapshot(run)
        if snapshot.get("score_schema_version") == SCORE_SCHEMA_VERSION:
            return 0
        if run.scoring_standard != "cx_eight_dimension":
            return 0

        rows = session.execute(
            select(CaseResultRow)
            .where(CaseResultRow.run_id == run.id)
            .order_by(CaseResultRow.id)
        ).scalars().all()
        if not rows:
            return 0
        results = [CaseResult.model_validate(row.detail_json) for row in rows]
        report_snapshot = {**snapshot, "scoring_standard": "cx_eight_dimension"}
        report = build_report(
            run_name=run.run_slug,
            results=results,
            adapter_type=run.adapter_type,
            config_snapshot=report_snapshot,
            description=run.description,
            started_at=run.started_at,
            n_runs=run.n_runs or 1,
        )
        pricing = report_snapshot.get("cost")
        for row, result in zip(rows, results, strict=True):
            update_case_row(row, build_case_row(run.id, result, pricing))
        populate_run_summary(run, report)
        updated_snapshot = _snapshot(run)
        updated_snapshot.update(
            {
                "score_schema_version": SCORE_SCHEMA_VERSION,
                "score_schema_migrated_at": _utcnow().isoformat(),
            }
        )
        run.config_snapshot = updated_snapshot
        return len(rows)


def recalculate_history_scores(
    settings: Settings | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """执行或预览护士 10 分制历史分数迁移。"""
    init_db(settings or get_settings())
    run_ids = _candidate_run_ids()
    if dry_run:
        return {
            "score_schema_version": SCORE_SCHEMA_VERSION,
            "status": "dry_run",
            "candidate_runs": len(run_ids),
            "run_ids": run_ids,
        }

    processed_runs = 0
    processed_cases = 0
    skipped_runs = 0
    errors: list[dict[str, Any]] = []
    for run_id in run_ids:
        try:
            case_count = _recalculate_run(run_id)
            if case_count:
                processed_runs += 1
                processed_cases += case_count
            else:
                skipped_runs += 1
        except Exception as exc:  # 记录后让下次发布从该 Run 继续，而不是掩盖问题。
            errors.append({"run_id": run_id, "error": str(exc)})

    details = {
        "score_schema_version": SCORE_SCHEMA_VERSION,
        "candidate_runs": len(run_ids),
        "processed_runs": processed_runs,
        "processed_cases": processed_cases,
        "skipped_runs": skipped_runs,
        "errors": errors[:20],
    }
    return {"status": "failed" if errors else "completed", **details}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="一次性重算历史 Agent 评测八维得分")
    parser.add_argument("--dry-run", action="store_true", help="仅展示待重算 Run，不写库")
    args = parser.parse_args(argv)
    result = recalculate_history_scores(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
