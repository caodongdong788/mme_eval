"""人工审核队列（HITL）：入队规则 / 裁定记录 / 统计 / 幂等迁移 / 不回写判分。"""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, select, text

from server.db import _ensure_additive_columns, session_scope
from server.models_db import CaseAnnotation, CaseResultRow, EvalRun


def _row(run_id, sample_id, *, level="L3", release_passed=True,
         needs_human_review=False, red_flag="none"):
    return CaseResultRow(
        run_id=run_id, sample_id=sample_id, scenario="x", level=level,
        release_passed=release_passed, needs_human_review=needs_human_review,
        composite_score=0.9,
        detail_json={"case": {"hard_gates": {"red_flag_triage": red_flag}}},
    )


def _seed_run(settings):
    """A=needs_human_review / B=红旗且失败 / C=普通通过。"""
    with session_scope() as s:
        run = EvalRun(run_slug="rq_2026-06-04_1", name="rq", status="success", n_runs=1)
        s.add(run)
        s.flush()
        rid = run.id
        s.add(_row(rid, "A", needs_human_review=True))
        s.add(_row(rid, "B", release_passed=False, red_flag="required_referral"))
        s.add(_row(rid, "C"))
    return rid


# ---------------------------------------------------------------------------
# 1. 入队规则

def test_queue_includes_needs_review_and_redflag_fail_only(client, settings):
    rid = _seed_run(settings)
    resp = client.get(f"/api/runs/{rid}/review-queue")
    assert resp.status_code == 200, resp.text
    items = {it["sample_id"]: it for it in resp.json()}
    assert set(items) == {"A", "B"}  # C 不入队
    assert "needs_human_review" in items["A"]["reasons"]
    assert "red_flag_failed" in items["B"]["reasons"]
    assert items["A"]["reviewed"] is False


def test_queue_includes_all_release_failed(client, settings):
    """普通上线失败（非红旗、非 needs_review）也入队，原因含 release_failed。"""
    with session_scope() as s:
        run = EvalRun(run_slug="rqf_1", name="rqf", status="success", n_runs=1)
        s.add(run)
        s.flush()
        rid = run.id
        s.add(_row(rid, "F", release_passed=False))  # 普通失败，非红旗
        s.add(_row(rid, "P", release_passed=True))    # 通过
    items = {it["sample_id"]: it for it in client.get(f"/api/runs/{rid}/review-queue").json()}
    assert set(items) == {"F"}
    assert "release_failed" in items["F"]["reasons"]


def test_failure_tag_labels_endpoint(client, settings):
    resp = client.get("/api/config/failure-tags")
    assert resp.status_code == 200
    labels = resp.json()
    assert labels and labels.get("missed_red_flag") == "漏报红旗"


# ---------------------------------------------------------------------------
# 2. 裁定记录

def test_annotate_persists_multiple(client, settings):
    rid = _seed_run(settings)
    assert client.post(f"/api/runs/{rid}/cases/A/annotate",
                       json={"verdict": "agree", "comment": "机器判对了"}).status_code == 201
    assert client.post(f"/api/runs/{rid}/cases/A/annotate",
                       json={"verdict": "override", "suggestion": "其实应救回"}).status_code == 201
    items = {it["sample_id"]: it for it in client.get(f"/api/runs/{rid}/review-queue").json()}
    assert items["A"]["reviewed"] is True
    assert len(items["A"]["annotations"]) == 2


def test_annotate_rejects_bad_verdict_and_unknown_case(client, settings):
    rid = _seed_run(settings)
    assert client.post(f"/api/runs/{rid}/cases/A/annotate",
                       json={"verdict": "maybe"}).status_code == 422
    assert client.post(f"/api/runs/{rid}/cases/ZZZ/annotate",
                       json={"verdict": "agree"}).status_code == 404


# ---------------------------------------------------------------------------
# 3. 统计

def test_cases_list_includes_latest_review_summary(client, settings):
    """/cases 每条用例附最新裁定摘要；无裁定为 null。"""
    rid = _seed_run(settings)
    client.post(f"/api/runs/{rid}/cases/A/annotate", json={"verdict": "agree", "comment": "c1"})
    client.post(f"/api/runs/{rid}/cases/A/annotate",
                json={"verdict": "override", "suggestion": "应救回", "comment": "c2"})
    rows = {r["sample_id"]: r for r in client.get(f"/api/runs/{rid}/cases").json()}
    # A 有裁定：取最新一条（override），count=2
    assert rows["A"]["review"]["verdict"] == "override"
    assert rows["A"]["review"]["suggestion"] == "应救回"
    assert rows["A"]["review"]["count"] == 2
    # C 无裁定
    assert rows["C"]["review"] is None


def test_review_stats(client, settings):
    rid = _seed_run(settings)
    client.post(f"/api/runs/{rid}/cases/A/annotate", json={"verdict": "agree"})
    stats = client.get(f"/api/runs/{rid}/review-stats").json()
    assert stats["queue_total"] == 2  # A,B
    assert stats["reviewed"] == 1 and stats["pending"] == 1
    assert stats["agree"] == 1 and stats["override"] == 0
    assert stats["agree_rate"] == 1.0 and stats["disagree_rate"] == 0.0


# ---------------------------------------------------------------------------
# 4. 不回写判分（旁路不变量）

def test_annotate_does_not_touch_scoring(client, settings):
    rid = _seed_run(settings)
    client.post(f"/api/runs/{rid}/cases/B/annotate", json={"verdict": "override"})
    with session_scope() as s:
        row = s.execute(
            select(CaseResultRow).where(
                CaseResultRow.run_id == rid, CaseResultRow.sample_id == "B")
        ).scalars().first()
        assert row.release_passed is False  # 维持原判
        assert row.composite_score == 0.9
        # 裁定独立落 case_annotation
        anns = s.execute(select(CaseAnnotation).where(
            CaseAnnotation.run_id == rid, CaseAnnotation.sample_id == "B")).scalars().all()
        assert len(anns) == 1 and anns[0].verdict == "override"


# ---------------------------------------------------------------------------
# 5. 幂等迁移

def test_ensure_additive_columns_auto_adds_drifted_columns(tmp_path):
    """历史漂移列（未手工登记）也应被 ORM 元数据驱动自动补齐。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'drift.db'}", future=True)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE eval_run (id INTEGER PRIMARY KEY, run_slug TEXT)"))
        conn.execute(text(
            "CREATE TABLE case_result (id INTEGER PRIMARY KEY, run_id INTEGER, sample_id TEXT)"))
    _ensure_additive_columns(engine)
    insp = inspect(engine)
    run_cols = {c["name"] for c in insp.get_columns("eval_run")}
    case_cols = {c["name"] for c in insp.get_columns("case_result")}
    assert "token_summary" in run_cols
    assert {"cost", "total_tokens"} <= case_cols


def test_ensure_additive_columns_backfills_null_json(tmp_path):
    """历史上以 NULL 形式补过的非空 JSON 列应被回填为合法空 JSON（修复响应 500）。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'nulljson.db'}", future=True)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE eval_run (id INTEGER PRIMARY KEY, run_slug TEXT, token_summary JSON)"))
        conn.execute(text(
            "INSERT INTO eval_run (id, run_slug, token_summary) VALUES (1, 'r', NULL)"))
    _ensure_additive_columns(engine)
    with engine.connect() as conn:
        val = conn.execute(text("SELECT token_summary FROM eval_run WHERE id=1")).scalar()
    assert val == "{}"
