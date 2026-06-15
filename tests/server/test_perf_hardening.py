"""B1 性能加固：运行列表分页、benchmark 用例读盘缓存、复合索引补建。"""

from __future__ import annotations

from sqlalchemy import inspect

from server.benchmarks import create_uploaded_benchmark, load_benchmark_cases
from server.db import get_sessionmaker, session_scope
from server.ingest import ingest_report

from factories import make_report

VALID_YAML = b"""
- sample_id: up_001
  scenario: \xe7\x97\x87\xe7\x8a\xb6
  level: L3
  score_profile: red_flag
  turns:
    - role: user
      content: x
""".strip()


# --- 分页 --------------------------------------------------------------------

def test_list_runs_default_returns_all(client, settings):
    with session_scope() as s:
        for i in range(3):
            ingest_report(s, make_report(run_name=f"r_{i}"))
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


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
