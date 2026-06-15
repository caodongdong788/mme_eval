"""rejudge_launch 服务层单测。"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text

from server import db as db_mod
from server.db import session_scope
from server.models_db import Benchmark, CaseResultRow, EvalRun, JudgeModelConfig
from server.schemas import RejudgeRequest
from server.services.rejudge_launch import (
    RejudgeLaunchError,
    resolve_judge_override,
    validate_rejudge_request,
)


def test_drop_review_requested_column(settings):
    """ORM 已移除 review_requested 时，init_db 应 DROP 遗留 NOT NULL 列。"""
    db_mod.reset_engine_for_tests()
    engine = db_mod.init_engine(settings)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS case_result"))
        conn.execute(
            text(
                "CREATE TABLE case_result ("
                "id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, "
                "sample_id VARCHAR(200) NOT NULL, "
                "review_requested BOOLEAN NOT NULL DEFAULT 0)"
            )
        )
    db_mod.init_db(settings)
    cols = {c["name"] for c in inspect(engine).get_columns("case_result")}
    assert "review_requested" not in cols


def test_resolve_judge_override_from_model_id(initialized_db, settings):
    with session_scope() as s:
        jm = JudgeModelConfig(
            name="j1", provider="openai", model="gpt-test", base_url="http://x"
        )
        s.add(jm)
        s.flush()
        ov = resolve_judge_override(s, RejudgeRequest(judge_model_id=jm.id))
    assert ov is not None
    assert ov.model == "gpt-test"
    assert ov.provider == "openai"


def test_resolve_judge_override_missing_model_404(initialized_db, settings):
    with session_scope() as s:
        with pytest.raises(RejudgeLaunchError) as exc:
            resolve_judge_override(s, RejudgeRequest(judge_model_id=9999))
    assert exc.value.status_code == 404


def test_validate_only_release_failed_requires_failures(initialized_db, settings):
    with session_scope() as s:
        run = EvalRun(run_slug="rj_val_1", name="r", status="success", n_runs=1)
        s.add(run)
        s.flush()
        s.add(
            CaseResultRow(
                run_id=run.id,
                sample_id="bc_001",
                scenario="x",
                release_passed=True,
                detail_json={},
            )
        )
        with pytest.raises(RejudgeLaunchError) as exc:
            validate_rejudge_request(
                s, run, RejudgeRequest(only_release_failed=True)
            )
    assert exc.value.status_code == 400
