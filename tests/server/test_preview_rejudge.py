"""单用例 ephemeral 试判预览 + cases-yaml 按 sample_id 过滤。

覆盖：preview_rejudge_case 套用判据覆盖并只判该条、端点返回 current/preview diff 且
零落库（不新建 run、不写 annotation）、404 未知用例、cases-yaml sample_id 过滤。
"""

from __future__ import annotations

import asyncio

import yaml
from factories import make_case_result, make_report
from sqlalchemy import func, select

from medeval import trace_store
from medeval.loader import load_cases
from medeval.reporter.aggregator import build_report
from server.db import session_scope
from server.eval_job import preview_rejudge_case
from server.models_db import Benchmark, CaseAnnotation, CaseResultRow, EvalRun
from factories import VALID_YAML_TEXT


def _seed_source_run(settings, *, n_runs: int = 1) -> int:
    """源 run：report.json + traces.jsonl.gz + CaseResultRow（含 detail_json）。"""
    report = make_report("pv_2026-06-08_1")
    report.n_runs = n_runs
    slug = report.run_name
    out_dir = settings.outputs_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(report.model_dump_json(), encoding="utf-8")
    cases = [r.case for r in report.results]
    per_case_traces = [[r.trace] for r in report.results]
    trace_store.write_traces(
        out_dir, cases, per_case_traces, store_raw="on_error",
        meta={"schema": trace_store.SCHEMA_VERSION, "adapter_fingerprint": "fp",
              "store_raw": "on_error", "n_runs": n_runs, "n_cases": len(cases)},
    )
    with session_scope() as s:
        bm = Benchmark(name="pv-bm", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        run = EvalRun(run_slug=slug, name="pv源", status="success",
                      benchmark_id=bm.id, n_runs=n_runs, has_traces=True)
        s.add(run)
        s.flush()
        rid = run.id
        for r in report.results:
            s.add(CaseResultRow(
                run_id=rid, sample_id=r.case.sample_id, scenario=r.case.scenario,
                level=r.case.level.value, release_passed=r.release_passed,
                detail_json=r.model_dump(mode="json"),
            ))
    return rid


# ---------------------------------------------------------------------------
# 1. service：套用判据覆盖并只对该单条用例判分


def test_preview_service_applies_override_single_case(initialized_db, settings, monkeypatch):
    rid = _seed_source_run(settings)
    captured: dict = {}

    async def fake_judge(config, cases, per_case_traces, judges, adjudicator, *,
                         progress=None, run_name=None, declare_plan=True, **kw):
        captured["ids"] = [c.sample_id for c in cases]
        captured["must_have"] = [
            p.keyword for p in cases[0].expected_behavior.must_have
        ]
        return build_report(run_name=run_name or "pv",
                            results=[make_case_result(cases[0].sample_id)],
                            adapter_type="openai_compat")

    monkeypatch.setattr("server.eval_job.judge_traces", fake_judge)

    result = asyncio.run(preview_rejudge_case(
        source_run_id=rid, sample_id="bc_001",
        case_override={"sample_id": "bc_001",
                       "expected_behavior": {"must_have": [{"keyword": "就医"}]}},
        settings=settings,
    ))
    # 只判该条；判据覆盖生效
    assert captured["ids"] == ["bc_001"]
    assert captured["must_have"] == ["就医"]
    assert result.case.sample_id == "bc_001"


def test_preview_service_unknown_sample_raises(initialized_db, settings):
    rid = _seed_source_run(settings)
    try:
        asyncio.run(preview_rejudge_case(
            source_run_id=rid, sample_id="nope", settings=settings,
        ))
        assert False, "未知用例应抛 ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# 2. 端点：返回 current/preview diff，且零落库（不新建 run、不写 annotation）


def test_preview_endpoint_returns_diff_zero_persist(client, settings, monkeypatch):
    rid = _seed_source_run(settings)

    async def fake_judge(config, cases, per_case_traces, judges, adjudicator, *,
                         progress=None, run_name=None, declare_plan=True, **kw):
        # 编辑判据后变为失败（与源 bc_001 通过相对）
        r = make_case_result(cases[0].sample_id, release_passed=False,
                             gate_passed=False, composite_score=0.4, grade="不合格")
        return build_report(run_name=run_name or "pv", results=[r],
                            adapter_type="openai_compat")

    monkeypatch.setattr("server.eval_job.judge_traces", fake_judge)

    with session_scope() as s:
        runs_before = s.scalar(select(func.count()).select_from(EvalRun))

    resp = client.post(
        f"/api/runs/{rid}/cases/bc_001/preview-rejudge",
        json={"case_override": {"sample_id": "bc_001",
                                "expected_behavior": {"must_have": [{"keyword": "就医"}]}}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sample_id"] == "bc_001"
    assert body["current"]["release_passed"] is True
    assert body["preview"]["release_passed"] is False
    assert body["changed"] is True
    assert body["case_result"]["case"]["sample_id"] == "bc_001"

    # 零落库：无新 run、无 annotation、源用例 detail 未变
    with session_scope() as s:
        runs_after = s.scalar(select(func.count()).select_from(EvalRun))
        ann = s.scalar(select(func.count()).select_from(CaseAnnotation))
        row = s.execute(select(CaseResultRow).where(
            CaseResultRow.run_id == rid, CaseResultRow.sample_id == "bc_001"
        )).scalars().first()
    assert runs_after == runs_before
    assert ann == 0
    assert row.detail_json["release_passed"] is True


def test_preview_endpoint_404_unknown_sample(client, settings):
    rid = _seed_source_run(settings)
    resp = client.post(f"/api/runs/{rid}/cases/zzz_999/preview-rejudge", json={})
    assert resp.status_code == 404


def test_preview_endpoint_accepts_yaml_text(client, settings, monkeypatch):
    rid = _seed_source_run(settings)
    captured: dict = {}

    async def fake_judge(config, cases, per_case_traces, judges, adjudicator, *,
                         progress=None, run_name=None, declare_plan=True, **kw):
        captured["must_have"] = [p.keyword for p in cases[0].expected_behavior.must_have]
        return build_report(run_name=run_name or "pv",
                            results=[make_case_result(cases[0].sample_id)],
                            adapter_type="openai_compat")

    monkeypatch.setattr("server.eval_job.judge_traces", fake_judge)

    yaml_text = (
        "- sample_id: bc_001\n  scenario: 症状\n  level: L3\n"
        "  turns:\n    - role: user\n      content: 我胸口痛\n"
        "  expected_behavior:\n    must_have:\n      - keyword: 立即就医\n"
    )
    resp = client.post(
        f"/api/runs/{rid}/cases/bc_001/preview-rejudge",
        json={"yaml_text": yaml_text},
    )
    assert resp.status_code == 200, resp.text
    assert captured["must_have"] == ["立即就医"]


def test_preview_endpoint_yaml_missing_sample_400(client, settings):
    rid = _seed_source_run(settings)
    resp = client.post(
        f"/api/runs/{rid}/cases/bc_001/preview-rejudge",
        json={"yaml_text": "- sample_id: other\n  scenario: x\n  level: L1\n"
                            "  turns:\n    - role: user\n      content: y\n"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 3. cases-yaml 按 sample_id 过滤：只返回单条用例 YAML（可被 loader 解析）


def test_cases_yaml_sample_id_filter_single(client, settings):
    up = client.post(
        "/api/benchmarks",
        files={"file": ("c.yaml", VALID_YAML_TEXT, "application/x-yaml")},
        data={"name": "pvy-src", "description": ""},
    )
    bm_id = up.json()["id"]
    with session_scope() as s:
        run = EvalRun(run_slug="pvy_2026-06-08_1", name="pvy", status="success",
                      benchmark_id=bm_id, n_runs=1)
        s.add(run)
        s.flush()
        run_id = run.id
        for sid, level in (("up_001", "L3"), ("up_002", "L1")):
            s.add(CaseResultRow(run_id=run_id, sample_id=sid, scenario="x",
                                level=level, release_passed=True))

    resp = client.get(f"/api/runs/{run_id}/cases-yaml", params={"sample_id": "up_001"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1
    parsed = yaml.safe_load(body["yaml_text"])
    assert [c["sample_id"] for c in parsed] == ["up_001"]
    tmp = settings.uploads_dir / "_pvy.yaml"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(body["yaml_text"], encoding="utf-8")
    assert load_cases(include=[str(tmp)], base_dir=settings.project_root)


def test_cases_yaml_sample_id_not_in_hits_400(client, settings):
    up = client.post(
        "/api/benchmarks",
        files={"file": ("c.yaml", VALID_YAML_TEXT, "application/x-yaml")},
        data={"name": "pvy-src2", "description": ""},
    )
    bm_id = up.json()["id"]
    with session_scope() as s:
        run = EvalRun(run_slug="pvy_2026-06-08_2", name="pvy2", status="success",
                      benchmark_id=bm_id, n_runs=1)
        s.add(run)
        s.flush()
        run_id = run.id
        s.add(CaseResultRow(run_id=run_id, sample_id="up_001", scenario="x",
                            level="L3", release_passed=True))

    resp = client.get(f"/api/runs/{run_id}/cases-yaml", params={"sample_id": "up_999"})
    assert resp.status_code == 400
