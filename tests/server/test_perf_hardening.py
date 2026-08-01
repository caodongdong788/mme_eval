"""B1 性能加固：运行列表分页、benchmark 用例读盘缓存、复合索引补建。"""

from __future__ import annotations

from sqlalchemy import inspect

from server.benchmarks import create_uploaded_benchmark, load_benchmark_cases
from server.db import get_sessionmaker, init_db, init_engine, session_scope
from server.ingest import ingest_report
from server.models_db import CaseResultRow

from factories import make_report

VALID_YAML = b"""
- schema_version: "2.0"
  sample_id: up_001
  scenario: \xe7\x97\x87\xe7\x8a\xb6
  level: L3
  turns:
    - role: user
      content: x
  evaluation: {}
""".strip()


# --- 分页 --------------------------------------------------------------------

def test_list_runs_default_limit_fifty(client, settings):
    with session_scope() as s:
        for i in range(3):
            ingest_report(s, make_report(run_name=f"r_{i}"))
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 3  # 不足默认 limit 时全返回


def test_list_runs_default_caps_at_fifty(client, settings):
    with session_scope() as s:
        for i in range(55):
            ingest_report(s, make_report(run_name=f"r_{i}"))
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 50


def test_list_runs_pagination_slices(client, settings):
    with session_scope() as s:
        for i in range(5):
            ingest_report(s, make_report(run_name=f"r_{i}"))
    resp = client.get("/api/runs", params={"limit": 2, "offset": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# --- benchmark 用例缓存 -------------------------------------------------------

def test_benchmark_cases_cached_and_isolated(initialized_db, settings):
    maker = get_sessionmaker()
    s = maker()
    try:
        bm = create_uploaded_benchmark(
            s, name="缓存集", content=VALID_YAML, filename="m.yaml", settings=settings
        )
        s.flush()
        first = load_benchmark_cases(bm, settings=settings)
        second = load_benchmark_cases(bm, settings=settings)
        # 两次解析内容一致，但返回独立对象（深拷贝隔离）。
        assert [c.sample_id for c in first] == [c.sample_id for c in second]
        assert first[0] is not second[0]
    finally:
        s.close()


# --- 复合索引 ----------------------------------------------------------------

def test_composite_indexes_created(initialized_db):
    maker = get_sessionmaker()
    s = maker()
    try:
        inspector = inspect(s.get_bind())
        names = {ix["name"] for ix in inspector.get_indexes("case_result")}
        assert "ix_case_result_run_sample" in names
        assert "ix_case_result_run_release" in names
        ann = {ix["name"] for ix in inspector.get_indexes("case_annotation")}
        assert "ix_case_annotation_run_sample" in ann
    finally:
        s.close()


def test_legacy_case_rows_are_backfilled_for_fast_list_columns(settings):
    """升级已有库时，只在首次补列时读取 detail_json 回填列表字段。"""
    engine = init_engine(settings)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE case_result (
                id INTEGER PRIMARY KEY,
                run_id INTEGER NOT NULL,
                sample_id VARCHAR(200), scenario VARCHAR(200), sub_scenario VARCHAR(200),
                level VARCHAR(20), source VARCHAR(40), tags JSON,
                medical_safety_passed BOOLEAN, release_passed BOOLEAN,
                composite_score FLOAT, guideline_earned FLOAT, guideline_max FLOAT,
                grade VARCHAR(20), stability VARCHAR(20), latency_ms FLOAT,
                total_tokens INTEGER, cost FLOAT, failure_tags JSON, detail_json JSON
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO case_result VALUES (
                1, 1, 'legacy_001', 's', '', 'L2', '', '[]', 1, 1,
                40, NULL, NULL, '优', 'stable_pass', NULL, NULL, NULL, '[]',
                '{"case":{"turns":[{"role":"user"},{"role":"assistant"},{"role":"user"}]},"trace":{"agent_chain":{"status":"synced","summary":{"sources":[{"key":"literature_rag","calls":1,"status":"hit"}]}}}}'
            )
            """
        )

    init_db(settings)
    with session_scope() as session:
        row = session.get(CaseResultRow, 1)
        assert row is not None
        assert row.n_turns == 2
        assert row.rag_status == "hit"

    names = {column["name"] for column in inspect(engine).get_columns("case_result")}
    assert {"n_turns", "rag_status"} <= names
