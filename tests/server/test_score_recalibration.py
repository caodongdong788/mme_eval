"""护士端改为原始 10 分后的历史结果重算测试。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from server.ingest import ingest_report
from server.models_db import CaseResultRow, EvalRun
from server.score_recalibration import (
    SCORE_SCHEMA_VERSION,
    _candidate_runs_query,
    recalculate_history_scores,
)

from factories import make_report


def test_candidate_query_is_postgresql_json_safe():
    sql = str(_candidate_runs_query().compile(dialect=postgresql.dialect()))
    assert "EXISTS" in sql
    assert "DISTINCT" not in sql


def test_history_score_recalibration_rewrites_existing_agent_eight_scores(session, initialized_db):
    report = make_report("legacy_nurse_score")
    report.config_snapshot = {"scoring_standard": "cx_eight_dimension"}
    run = ingest_report(session, report)
    run.scoring_standard = "cx_eight_dimension"
    session.commit()
    run_id = run.id

    result = recalculate_history_scores(initialized_db)
    assert result["status"] == "completed"
    assert result["processed_runs"] == 1
    assert result["processed_cases"] == 2

    session.expire_all()
    updated_run = session.get(EvalRun, run_id)
    assert updated_run is not None
    assert updated_run.config_snapshot["score_schema_version"] == SCORE_SCHEMA_VERSION
    rows = session.execute(
        select(CaseResultRow).where(CaseResultRow.run_id == run_id).order_by(CaseResultRow.id)
    ).scalars().all()
    # 第一条八维均为 5 分；第二条保留原有 2 分短板，只改变护士端满分口径。
    assert [row.composite_score for row in rows] == [40.0, 19.0]
    assert [row.detail_json["end_scores"]["nurse"] for row in rows] == [10.0, 4.0]
    assert [sum(row.detail_json["end_scores"].values()) for row in rows] == [40.0, 19.0]
    assert updated_run.grading["avg_composite"] == 29.5

    repeated = recalculate_history_scores(initialized_db)
    assert repeated["status"] == "completed"
    assert repeated["candidate_runs"] == 0
    assert repeated["processed_runs"] == 0


def test_history_score_recalibration_skips_model_comparison_runs(session, initialized_db):
    report = make_report("model_comparison_history")
    report.config_snapshot = {"scoring_standard": "model_comparison"}
    run = ingest_report(session, report)
    run.scoring_standard = "model_comparison"
    session.commit()

    result = recalculate_history_scores(initialized_db)
    assert result["status"] == "completed"
    assert result["candidate_runs"] == 0
    session.expire_all()
    row = session.execute(select(CaseResultRow).order_by(CaseResultRow.id)).scalars().first()
    assert row is not None
    assert row.detail_json["end_scores"]["nurse"] == 15
