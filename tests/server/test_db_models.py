"""ORM 表结构与 JSON 列往返测试。"""

from __future__ import annotations

from sqlalchemy import inspect, select

from server.db import get_sessionmaker
from server.models_db import Benchmark, CaseResultRow, EvalRun


def test_tables_created(initialized_db):
    maker = get_sessionmaker()
    s = maker()
    try:
        names = set(inspect(s.get_bind()).get_table_names())
        assert {"benchmark", "eval_run", "case_result"} <= names
        case_cols = {c["name"] for c in inspect(s.get_bind()).get_columns("case_result")}
        run_cols = {c["name"] for c in inspect(s.get_bind()).get_columns("eval_run")}
        benchmark_cols = {c["name"] for c in inspect(s.get_bind()).get_columns("benchmark")}
        assert "population" not in case_cols
        assert "difficulty" not in case_cols
        assert "by_population" not in run_cols
        assert "by_difficulty" not in run_cols
        assert "ttft_ms" in case_cols
        assert "case_type" in case_cols
        assert "ttft_summary" in run_cols
        assert "by_case_type" in run_cols
        assert "updated_at" in benchmark_cols
    finally:
        s.close()


def test_benchmark_json_roundtrip(session):
    bm = Benchmark(
        name="乳腺癌专科",
        description="builtin",
        source="builtin",
        case_count=71,
        tags=["medical", "v2"],
        storage_path="cases/benchmark",
    )
    session.add(bm)
    session.commit()

    got = session.execute(select(Benchmark)).scalar_one()
    assert got.id is not None
    assert got.tags == ["medical", "v2"]
    assert got.case_count == 71
    assert got.created_at is not None
    assert got.updated_at is not None


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
        grading={"avg_composite": 37.35},
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
        medical_safety_passed=True,
        composite_score=32.4,
        grade="良好",
        stability="flaky",
        failure_tags=["adapter_error"],
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
    assert got_cr.medical_safety_passed is True
    assert got_cr.failure_tags == ["adapter_error"]
    assert got_cr.detail_json["trace"]["messages"][0]["content"] == "hi"
