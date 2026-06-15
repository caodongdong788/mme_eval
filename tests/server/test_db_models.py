"""ORM 表结构与 JSON 列往返测试。"""

from __future__ import annotations

from sqlalchemy import inspect, select, text

from server import db as db_mod
from server.db import get_sessionmaker
from server.models_db import Benchmark, CaseResultRow, EvalRun


def test_drop_obsolete_columns_with_index_does_not_crash(settings):
    """旧库 case_result.population 带索引时，init_db 必须先删索引再 DROP COLUMN，不得崩。

    回归 remove-population-difficulty-db 引入的启动崩溃：SQLite 无法 DROP 仍被索引引用的列。
    """
    db_mod.reset_engine_for_tests()
    engine = db_mod.init_engine(settings)
    # 造一张含 population 列 + 其索引的「旧」case_result 表。
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS case_result"))
        conn.execute(
            text(
                "CREATE TABLE case_result ("
                "id INTEGER PRIMARY KEY, run_id INTEGER, sample_id VARCHAR(200), "
                "population VARCHAR(40), difficulty VARCHAR(20))"
            )
        )
        conn.execute(
            text("CREATE INDEX ix_case_result_population ON case_result (population)")
        )
    # init_db 应幂等清掉旧列（含先删索引），不抛错。
    db_mod.init_db(settings)
    cols = {c["name"] for c in inspect(engine).get_columns("case_result")}
    assert "population" not in cols
    assert "difficulty" not in cols


def test_tables_created(initialized_db):
    maker = get_sessionmaker()
    s = maker()
    try:
        names = set(inspect(s.get_bind()).get_table_names())
        assert {"benchmark", "eval_run", "case_result"} <= names
        case_cols = {c["name"] for c in inspect(s.get_bind()).get_columns("case_result")}
        run_cols = {c["name"] for c in inspect(s.get_bind()).get_columns("eval_run")}
        assert "population" not in case_cols
        assert "difficulty" not in case_cols
        assert "by_population" not in run_cols
        assert "by_difficulty" not in run_cols
    finally:
        s.close()


def test_benchmark_json_roundtrip(session):
    bm = Benchmark(
        name="乳腺癌专科",
        description="builtin",
        source="builtin",
        case_count=71,
        tags=["red_flag", "adversarial"],
        storage_path="cases/breast_cancer",
    )
    session.add(bm)
    session.commit()

    got = session.execute(select(Benchmark)).scalar_one()
    assert got.id is not None
    assert got.tags == ["red_flag", "adversarial"]
    assert got.case_count == 71
    assert got.created_at is not None


def test_run_and_case_relationship_and_json(session):
    run = EvalRun(
        run_slug="doubao_2026-06-03_1",
        name="doubao",
        status="success",
        adapter_type="openai_compat",
        judge_overrides={"model": "gpt-4o", "provider": "openai"},
        total=2,
        passed=1,
        pass_rate=0.5,
        grading={"avg_composite": 0.83},
        by_level={"L3": {"total": 1, "passed": 1}},
    )
    session.add(run)
    session.flush()  # 拿到 run.id

    cr = CaseResultRow(
        run_id=run.id,
        sample_id="bc_001",
        scenario="症状",
        level="L3",
        release_passed=False,
        composite_score=0.72,
        grade="良好",
        score_profile="knowledge",
        stability="flaky",
        failure_tags=["missed_red_flag"],
        detail_json={"trace": {"messages": [{"role": "user", "content": "hi"}]}, "verdicts": []},
    )
    session.add(cr)
    session.commit()

    got_run = session.execute(select(EvalRun)).scalar_one()
    assert got_run.judge_overrides["model"] == "gpt-4o"
    assert got_run.by_level["L3"]["passed"] == 1
    assert len(got_run.case_results) == 1

    got_cr = got_run.case_results[0]
    assert got_cr.release_passed is False
    assert got_cr.failure_tags == ["missed_red_flag"]
    assert got_cr.detail_json["trace"]["messages"][0]["content"] == "hi"
