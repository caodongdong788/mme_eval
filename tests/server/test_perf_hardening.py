"""B1 性能加固：运行列表分页、benchmark 用例读盘缓存、复合索引补建。"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import event, inspect

from server.benchmarks import create_uploaded_benchmark, load_benchmark_cases
from server.db import get_sessionmaker, init_db, init_engine, session_scope
from server.ingest import ingest_report
from server.models_db import Benchmark, CaseAnnotation, CaseResultRow, EvalRun
from server.services.case_query import attach_review_summary
from server.services.dashboard import benchmark_trends
from server.services.open_api_config import authorize_open_api_key, create_open_api_key

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
                '{"case":{"case_type":"follow_up","turns":[{"role":"user"},{"role":"assistant"},{"role":"user"}]},"trace":{"agent_chain":{"status":"synced","summary":{"sources":[{"key":"literature_rag","calls":1,"status":"hit"}]}}}}'
            )
            """
        )

    init_db(settings)
    with session_scope() as session:
        row = session.get(CaseResultRow, 1)
        assert row is not None
        assert row.case_type == "follow_up"
        assert row.n_turns == 2
        assert row.rag_status == "hit"

    names = {column["name"] for column in inspect(engine).get_columns("case_result")}
    assert {"case_type", "n_turns", "rag_status"} <= names


def test_repeated_init_does_not_rescan_case_detail_json(initialized_db, session) -> None:
    """普通进程重启不能再次执行读取大 JSON 的历史判分回填。"""
    run = EvalRun(run_slug="already-migrated")
    session.add(run)
    session.flush()
    row = CaseResultRow(
        run_id=run.id,
        sample_id="case_large_detail",
        judge_error=False,
        detail_json={
            "verdicts": [{
                "name": "guideline.legacy",
                "reason": "指南判分失败：历史内容只允许显式维护时重扫",
            }],
            "large_payload": "x" * 10_000,
        },
    )
    session.add(row)
    session.commit()

    init_db(initialized_db)
    session.expire_all()

    # judge_error 列早已存在，重复 init_db 应直接返回，不能把历史明细再读写一遍。
    assert session.get(CaseResultRow, row.id).judge_error is False


def test_valid_open_api_auth_uses_one_index_lookup(initialized_db) -> None:
    """高频成功鉴权不能先额外扫描一次“是否存在任意 Key”。"""
    with session_scope() as session:
        _, raw_key = create_open_api_key(
            session,
            name="鉴权查询计数",
            permissions=["benchmarks:read"],
            created_by="test",
        )

    engine = init_engine(initialized_db)
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with session_scope() as session:
            authorize_open_api_key(session, raw_key, "benchmarks:read")
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    key_selects = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
        and "open_api_access_key" in statement.lower()
    ]
    assert len(key_selects) == 1


def test_open_api_recent_use_does_not_write_on_every_request(initialized_db) -> None:
    """一分钟内重复鉴权只读索引，避免热点 Key 持续争抢数据库写锁。"""
    with session_scope() as session:
        _, raw_key = create_open_api_key(
            session,
            name="鉴权写锁降采样",
            permissions=["benchmarks:read"],
            created_by="test",
        )
    with session_scope() as session:
        authorize_open_api_key(session, raw_key, "benchmarks:read")

    engine = init_engine(initialized_db)
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with session_scope() as session:
            authorize_open_api_key(session, raw_key, "benchmarks:read")
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert not any(
        statement.lstrip().upper().startswith("UPDATE OPEN_API_ACCESS_KEY")
        for statement in statements
    )


def test_review_summary_aggregates_history_in_database(session) -> None:
    """列表只取每题最新审核与计数，不把全部历史评论对象装入内存。"""
    run = EvalRun(run_slug="review-summary-perf", status="success")
    session.add(run)
    session.flush()
    case = CaseResultRow(run_id=run.id, sample_id="case-1")
    session.add(case)
    session.flush()
    started = datetime(2026, 1, 1)
    session.add_all(
        [
            CaseAnnotation(
                run_id=run.id,
                sample_id=case.sample_id,
                verdict="agree" if index < 99 else "override",
                reviewer=f"reviewer-{index}",
                comment=f"comment-{index}",
                created_at=started + timedelta(seconds=index),
            )
            for index in range(100)
        ]
    )
    session.commit()

    attach_review_summary(session, run.id, [case])

    assert case.review.count == 100
    assert case.review.verdict == "override"
    assert case.review.reviewer == "reviewer-99"
    assert case.review.comment == "comment-99"


def test_trend_query_does_not_lazy_load_omitted_run_columns(session) -> None:
    """趋势接口只读取展示列，且不会因遗漏字段退化成逐 Run 懒加载。"""
    benchmark = Benchmark(name="趋势列裁剪", source="offline")
    session.add(benchmark)
    session.flush()
    session.add_all(
        [
            EvalRun(
                run_slug=f"trend-{index}",
                name=f"trend-{index}",
                benchmark_id=benchmark.id,
                status="success",
                grading={"avg_composite": 40 + index},
                config_snapshot={"large": "x" * 10_000},
            )
            for index in range(10)
        ]
    )
    session.commit()
    benchmark_id = benchmark.id
    session.expire_all()

    engine = session.get_bind()
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        result = benchmark_trends(session, benchmark_id)
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert len(result["points"]) == 10
    assert len(statements) == 1
    assert "config_snapshot" not in statements[0]
