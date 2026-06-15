"""用例列表按指南匹配率过滤：full(=1.0) / partial(非空且<1) / none(空)。"""

from __future__ import annotations

from server.db import session_scope
from server.models_db import CaseResultRow, EvalRun


def _seed(settings) -> int:
    with session_scope() as s:
        run = EvalRun(run_slug="g_2026-06-05_1", name="g", status="success", n_runs=1)
        s.add(run)
        s.flush()
        rid = run.id
        rows = [
            ("full", 1.0),
            ("part", 0.5),
            ("none", None),
        ]
        for sid, rate in rows:
            s.add(CaseResultRow(run_id=rid, sample_id=sid, scenario="x",
                                level="L1", release_passed=True,
                                guideline_match_rate=rate))
        return rid


def test_no_filter_returns_all(client, settings):
    rid = _seed(settings)
    ids = {r["sample_id"] for r in client.get(f"/api/runs/{rid}/cases").json()}
    assert ids == {"full", "part", "none"}


def test_filter_guideline_full(client, settings):
    rid = _seed(settings)
    ids = {r["sample_id"]
           for r in client.get(f"/api/runs/{rid}/cases", params={"guideline": "full"}).json()}
    assert ids == {"full"}


def test_filter_guideline_partial(client, settings):
    rid = _seed(settings)
    ids = {r["sample_id"]
           for r in client.get(f"/api/runs/{rid}/cases", params={"guideline": "partial"}).json()}
    assert ids == {"part"}


def test_filter_guideline_none(client, settings):
    rid = _seed(settings)
    ids = {r["sample_id"]
           for r in client.get(f"/api/runs/{rid}/cases", params={"guideline": "none"}).json()}
    assert ids == {"none"}
