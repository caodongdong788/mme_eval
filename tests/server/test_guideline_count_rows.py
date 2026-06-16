"""用例列表指南匹配率带命中计数：服务端从 detail_json 派生 guideline_matched/total。"""

from __future__ import annotations

from server.db import session_scope
from server.models_db import Benchmark, CaseResultRow, EvalRun


def _seed_run_with_cases(settings):
    with session_scope() as s:
        bm = Benchmark(name="b", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        run = EvalRun(
            run_slug="r_2026-06-05_1", name="r", status="success", benchmark_id=bm.id
        )
        s.add(run)
        s.flush()

        # 用例 A：3 个带指南锚点的得分点（idx0/1/2），命中 idx0、idx2 → 2/3。
        s.add(
            CaseResultRow(
                run_id=run.id,
                sample_id="bc_a",
                scenario="筛查",
                guideline_match_rate=2 / 3,
                detail_json={
                    "case": {
                        "scoring_points": [
                            {"criterion": "x", "points": 1, "guideline": "NCCN-1"},
                            {"criterion": "y", "points": 1, "guideline": "NCCN-2"},
                            {"criterion": "z", "points": -1, "guideline": "NCCN-3"},
                            {"criterion": "w", "points": 1, "guideline": None},
                        ]
                    },
                    "verdicts": [
                        {"name": "scoring_point.point0", "passed": True},
                        {"name": "scoring_point.point1", "passed": False},
                        {"name": "scoring_point.point2", "passed": True},
                        {"name": "scoring_point.point3", "passed": True},
                        {"name": "scoring_point.summary", "passed": False},
                    ],
                },
            )
        )
        # 用例 B：无带指南锚点的得分点 → 计数应为 None。
        s.add(
            CaseResultRow(
                run_id=run.id,
                sample_id="bc_b",
                scenario="症状",
                guideline_match_rate=None,
                detail_json={"case": {"scoring_points": []}, "verdicts": []},
            )
        )
        s.flush()
        return run.id


def test_case_rows_list_omits_guideline_counts(client, settings):
    """列表路径不加载 detail_json，指南命中计数仅在明细/导出路径计算。"""
    run_id = _seed_run_with_cases(settings)
    resp = client.get(f"/api/runs/{run_id}/cases")
    assert resp.status_code == 200, resp.text
    by_id = {r["sample_id"]: r for r in resp.json()}

    assert by_id["bc_a"]["guideline_matched"] is None
    assert by_id["bc_a"]["guideline_total"] is None
    assert by_id["bc_b"]["guideline_matched"] is None
    assert by_id["bc_b"]["guideline_total"] is None


def test_guideline_counts_with_detail_json(client, settings):
    from server.db import session_scope
    from server.services.case_query import filtered_case_rows

    run_id = _seed_run_with_cases(settings)
    with session_scope() as s:
        rows = filtered_case_rows(s, run_id, load_detail_json=True)
    by_id = {r.sample_id: r for r in rows}
    assert by_id["bc_a"].guideline_matched == 2
    assert by_id["bc_a"].guideline_total == 3
    assert by_id["bc_b"].guideline_matched is None
    assert by_id["bc_b"].guideline_total is None
