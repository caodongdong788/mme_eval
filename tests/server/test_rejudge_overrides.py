"""可换 judge 模型重判 + 改 case 判据派生新 benchmark + 上传人。

覆盖：build_rejudge_job 应用 judge/cases_benchmark_id 覆盖、
derive_benchmark_with_overrides 派生且不改源、非法 override 拒绝、created_by 落库与端点。
"""

from __future__ import annotations

import asyncio

import yaml
from factories import VALID_YAML_TEXT, make_report
from sqlalchemy import select

from factories import make_case_result
from medeval import trace_store
from medeval.loader import load_cases
from medeval.models import JudgeVerdict
from medeval.reporter.aggregator import build_report
from server.benchmarks import (
    BenchmarkValidationError,
    create_uploaded_benchmark,
    derive_benchmark_from_yaml,
    derive_benchmark_with_overrides,
    load_benchmark_cases,
)
from server.db import session_scope
from server.eval_job import build_rejudge_job
from server.models_db import Benchmark, CaseResultRow, EvalRun, JudgeModelConfig
from server.progress import InMemoryProgress


# ---------------------------------------------------------------------------
# 源 run：report.json + traces.jsonl.gz（sample_id 与 derive 用例对齐）


def _seed_source_run(settings, *, sample_ids=("bc_001", "bc_002"), n_runs: int = 1) -> int:
    report = make_report("ov_2026-06-04_1")
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
        bm = Benchmark(name="src-bm", source="uploaded", storage_path="/tmp/none")
        s.add(bm)
        s.flush()
        row = EvalRun(run_slug=slug, name="源", status="success",
                      benchmark_id=bm.id, n_runs=n_runs, has_traces=True)
        s.add(row)
        s.flush()
        return row.id


# ---------------------------------------------------------------------------
# 1. build_rejudge_job 应用 judge 覆盖（传给 judge_traces 的 config 已改模型）


def test_rejudge_job_applies_judge_override(initialized_db, settings, monkeypatch):
    src_id = _seed_source_run(settings)
    with session_scope() as s:
        new = EvalRun(run_slug="(pending)", name="重判", status="pending", parent_run_id=src_id)
        s.add(new)
        s.flush()
        new_id = new.id

    captured: dict = {}

    async def fake_judge(config, cases, per_case_traces, judges, adjudicator, *,
                         progress=None, run_name=None, declare_plan=True, **kw):
        captured["model"] = config.judges.llm.model
        return make_report(run_name or "rj_2026-06-04_1")

    monkeypatch.setattr("server.eval_job.judge_traces", fake_judge)

    job = build_rejudge_job(
        new_id, source_run_id=src_id, run_name="重判", settings=settings,
        judge_override={"model": "gpt-4o-mega"},
    )
    asyncio.run(job(InMemoryProgress()))
    assert captured["model"] == "gpt-4o-mega"


# ---------------------------------------------------------------------------
# 2. build_rejudge_job 用 cases_benchmark_id 的改后判据替换冻结用例


def test_rejudge_job_uses_cases_benchmark_overrides(initialized_db, settings, monkeypatch):
    src_id = _seed_source_run(settings)
    # 派生一个把 bc_001 的 must_have 改掉的 benchmark
    with session_scope() as s:
        src_bm = Benchmark(name="seed-derive-src", source="uploaded", storage_path="/tmp/none")
        s.add(src_bm)
        s.flush()
        src_bm_id = s.scalar(select(Benchmark.id).where(Benchmark.name == "seed-derive-src"))

    # 用真实可加载用例集做派生源（含 bc_001 / bc_002 同名）
    yaml_text = (
        "- sample_id: bc_001\n  scenario: 症状\n  level: L3\n  turns:\n"
        "    - role: user\n      content: 我胸口痛\n"
        "- sample_id: bc_002\n  scenario: 筛查\n  level: L1\n  turns:\n"
        "    - role: user\n      content: 多久筛查\n"
    )
    with session_scope() as s:
        bm = create_uploaded_benchmark(
            s, name="derive-source-real", content=yaml_text.encode(), settings=settings)
        s.flush()
        derived = derive_benchmark_with_overrides(
            s, bm, name="edited-bm", created_by="测试员",
            case_overrides=[{"sample_id": "bc_001",
                             "expected_behavior": {"must_have": [{"keyword": "就医"}]}}],
            settings=settings,
        )
        s.flush()
        edited_bm_id = derived.id

    captured: dict = {}

    async def fake_judge(config, cases, per_case_traces, judges, adjudicator, *,
                         progress=None, run_name=None, declare_plan=True, **kw):
        by_id = {c.sample_id: c for c in cases}
        captured["bc_001_must_have"] = [
            p.keyword for p in by_id["bc_001"].expected_behavior.must_have
        ]
        return make_report(run_name or "rj_2026-06-04_1")

    monkeypatch.setattr("server.eval_job.judge_traces", fake_judge)

    with session_scope() as s:
        new = EvalRun(run_slug="(pending)", name="重判2", status="pending", parent_run_id=src_id)
        s.add(new)
        s.flush()
        new_id = new.id

    job = build_rejudge_job(
        new_id, source_run_id=src_id, run_name="重判2", settings=settings,
        cases_benchmark_id=edited_bm_id,
    )
    asyncio.run(job(InMemoryProgress()))
    assert captured["bc_001_must_have"] == ["就医"]


# ---------------------------------------------------------------------------
# 4. derive：派生新 benchmark，源不变，created_by 落库


def test_derive_benchmark_forks_and_preserves_source(initialized_db, settings):
    with session_scope() as s:
        src = create_uploaded_benchmark(
            s, name="orig", content=VALID_YAML_TEXT.encode(), settings=settings)
        s.flush()
        derived = derive_benchmark_with_overrides(
            s, src, name="orig-fork", created_by="张三",
            case_overrides=[{"sample_id": "up_001",
                             "hard_gates": {"require_disclaimer": True}}],
            settings=settings,
        )
        s.flush()
        src_id, derived_id = src.id, derived.id

    with session_scope() as s:
        src = s.get(Benchmark, src_id)
        derived = s.get(Benchmark, derived_id)
        assert derived.id != src.id
        assert derived.created_by == "张三"
        assert derived.source == "uploaded"
        # 源用例判据不变（require_disclaimer 默认 False）
        src_cases = {c.sample_id: c for c in load_benchmark_cases(src, settings=settings)}
        derived_cases = {c.sample_id: c for c in load_benchmark_cases(derived, settings=settings)}
        assert src_cases["up_001"].hard_gates.require_disclaimer is False
        assert derived_cases["up_001"].hard_gates.require_disclaimer is True


def test_derive_rejects_invalid_override(initialized_db, settings):
    with session_scope() as s:
        src = create_uploaded_benchmark(
            s, name="orig2", content=VALID_YAML_TEXT.encode(), settings=settings)
        s.flush()
        try:
            derive_benchmark_with_overrides(
                s, src, name="orig2-bad", created_by="x",
                case_overrides=[{"sample_id": "up_001",
                                 "hard_gates": {"red_flag_triage": "not_a_level"}}],
                settings=settings,
            )
            assert False, "应拒绝非法 hard_gates"
        except BenchmarkValidationError:
            pass


# ---------------------------------------------------------------------------
# 5. 端点


def test_rejudge_endpoint_accepts_judge_override(client, settings, monkeypatch):
    src_id = _seed_source_run(settings)
    captured: dict = {}

    def fake_builder(new_id, **kw):
        captured.update(kw)

        async def job(progress):
            return None
        return job

    monkeypatch.setattr("server.routers.runs.build_rejudge_job", fake_builder)
    resp = client.post(
        f"/api/runs/{src_id}/rejudge",
        json={"judge": {"model": "gpt-4o-mega"}},
    )
    assert resp.status_code == 201, resp.text
    assert (captured.get("judge_override") or {}).get("model") == "gpt-4o-mega"


def test_rejudge_endpoint_400_on_missing_cases_benchmark(client, settings):
    src_id = _seed_source_run(settings)
    resp = client.post(
        f"/api/runs/{src_id}/rejudge", json={"cases_benchmark_id": 99999})
    assert resp.status_code == 400


def test_derive_endpoint_creates_benchmark(client, settings):
    # 先建一个源 benchmark
    up = client.post(
        "/api/benchmarks",
        files={"file": ("c.yaml", VALID_YAML_TEXT, "application/x-yaml")},
        data={"name": "ep-src", "description": ""},
    )
    assert up.status_code == 201, up.text
    src_id = up.json()["id"]

    resp = client.post(
        f"/api/benchmarks/{src_id}/derive",
        json={"name": "ep-fork", "description": "派生",
              "case_overrides": [{"sample_id": "up_001",
                                  "hard_gates": {"require_disclaimer": True}}]},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "ep-fork"
    assert body["source"] == "uploaded"
    assert "created_by" in body


def test_benchmark_out_exposes_created_by(client, settings):
    client.post(
        "/api/benchmarks",
        files={"file": ("c.yaml", VALID_YAML_TEXT, "application/x-yaml")},
        data={"name": "cb", "description": ""},
    )
    resp = client.get("/api/benchmarks")
    assert resp.status_code == 200
    assert all("created_by" in b for b in resp.json())


# ---------------------------------------------------------------------------
# 6. YAML 在线改判据 → 另存新 benchmark（解耦）

_EDIT_YAML = """
- sample_id: up_001
  scenario: 症状
  level: L3
  score_profile: red_flag
  turns:
    - role: user
      content: 这段改动应被忽略（只合并判据字段）
  hard_gates:
    require_disclaimer: true
- sample_id: zzz_999
  scenario: 不存在
  level: L1
  turns:
    - role: user
      content: x
  hard_gates:
    require_disclaimer: true
""".strip()


def test_derive_from_yaml_only_judging_fields_and_discards_unmatched(
    initialized_db, settings
):
    with session_scope() as s:
        src = create_uploaded_benchmark(
            s, name="yaml-src", content=VALID_YAML_TEXT.encode(), settings=settings)
        s.flush()
        derived = derive_benchmark_from_yaml(
            s, src, name="yaml-fork", yaml_text=_EDIT_YAML,
            created_by="李四", settings=settings)
        s.flush()
        src_id, derived_id = src.id, derived.id

    with session_scope() as s:
        src = s.get(Benchmark, src_id)
        derived = s.get(Benchmark, derived_id)
        assert derived.created_by == "李四"
        d = {c.sample_id: c for c in load_benchmark_cases(derived, settings=settings)}
        srcc = {c.sample_id: c for c in load_benchmark_cases(src, settings=settings)}
        # 判据字段生效
        assert d["up_001"].hard_gates.require_disclaimer is True
        # turns 不被合并（仍为源用例原文）
        assert d["up_001"].turns[0].content == srcc["up_001"].turns[0].content
        # 未匹配 sample_id 丢弃
        assert "zzz_999" not in d
        # 未出现在 YAML 的源用例保持原样
        assert d["up_002"].hard_gates.require_disclaimer is False
        # 源集不变
        assert srcc["up_001"].hard_gates.require_disclaimer is False


def test_derive_from_yaml_zero_match_raises(initialized_db, settings):
    with session_scope() as s:
        src = create_uploaded_benchmark(
            s, name="yaml-src2", content=VALID_YAML_TEXT.encode(), settings=settings)
        s.flush()
        try:
            derive_benchmark_from_yaml(
                s, src, name="yaml-fork2",
                yaml_text="- sample_id: nope\n  hard_gates: {require_disclaimer: true}\n",
                created_by="x", settings=settings)
            assert False, "零匹配应报错"
        except BenchmarkValidationError:
            pass


def test_derive_yaml_endpoint_creates_benchmark(client, settings):
    up = client.post(
        "/api/benchmarks",
        files={"file": ("c.yaml", VALID_YAML_TEXT, "application/x-yaml")},
        data={"name": "yep-src", "description": ""},
    )
    src_id = up.json()["id"]
    resp = client.post(
        f"/api/benchmarks/{src_id}/derive-yaml",
        json={"name": "yep-fork", "description": "y", "yaml_text": _EDIT_YAML},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "yep-fork"


# ---------------------------------------------------------------------------
# 7. cases-yaml 预填：按过滤返回命中用例完整 YAML


def test_cases_yaml_endpoint_filters(client, settings):
    up = client.post(
        "/api/benchmarks",
        files={"file": ("c.yaml", VALID_YAML_TEXT, "application/x-yaml")},
        data={"name": "cy-src", "description": ""},
    )
    bm_id = up.json()["id"]
    with session_scope() as s:
        run = EvalRun(run_slug="cy_2026-06-04_1", name="cy", status="success",
                      benchmark_id=bm_id, n_runs=1)
        s.add(run)
        s.flush()
        run_id = run.id
        for sid, level in (("up_001", "L3"), ("up_002", "L1")):
            s.add(CaseResultRow(run_id=run_id, sample_id=sid, scenario="x",
                                level=level, release_passed=True))

    resp = client.get(f"/api/runs/{run_id}/cases-yaml", params={"level": "L3"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1
    # 返回的 YAML 仅含命中的 up_001，且可被 loader 解析
    parsed = yaml.safe_load(body["yaml_text"])
    assert [c["sample_id"] for c in parsed] == ["up_001"]
    tmp = settings.uploads_dir / "_cy.yaml"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(body["yaml_text"], encoding="utf-8")
    assert load_cases(include=[str(tmp)], base_dir=settings.project_root)


# ---------------------------------------------------------------------------
# 8. 只重判上线失败用例：判失败子集 + 合并源报告通过用例 + 整体重算


def test_rejudge_job_only_release_failed_merges_passed(initialized_db, settings, monkeypatch):
    # 源报告：bc_001 通过、bc_002 失败 → 只重判 bc_002，bc_001 沿用源结果
    src_id = _seed_source_run(settings)
    with session_scope() as s:
        new = EvalRun(run_slug="(pending)", name="只重失败", status="pending", parent_run_id=src_id)
        s.add(new)
        s.flush()
        new_id = new.id

    captured: dict = {}

    async def fake_judge(config, cases, per_case_traces, judges, adjudicator, *,
                         progress=None, run_name=None, declare_plan=True, **kw):
        captured["judged_ids"] = [c.sample_id for c in cases]
        results = []
        for c in cases:
            r = make_case_result(c.sample_id, release_passed=True, gate_passed=True)
            r.verdicts.append(JudgeVerdict(name="rejudged.marker", passed=True))
            results.append(r)
        return build_report(run_name=run_name or "rj", results=results,
                            adapter_type="openai_compat")

    def fake_persist(run_id, report, out_dir, **kw):
        captured["report"] = report

    monkeypatch.setattr("server.eval_job.judge_traces", fake_judge)
    monkeypatch.setattr("server.eval_job._persist_outcome", fake_persist)

    job = build_rejudge_job(
        new_id, source_run_id=src_id, run_name="只重失败", settings=settings,
        only_release_failed=True,
    )
    asyncio.run(job(InMemoryProgress()))

    # 只对失败用例 bc_002 重判
    assert captured["judged_ids"] == ["bc_002"]
    # 合并报告含两条用例
    by_id = {r.case.sample_id: r for r in captured["report"].results}
    assert set(by_id) == {"bc_001", "bc_002"}
    # bc_002 用新结果（带 marker），bc_001 沿用源（无 marker）
    assert any(v.name == "rejudged.marker" for v in by_id["bc_002"].verdicts)
    assert not any(v.name == "rejudged.marker" for v in by_id["bc_001"].verdicts)


def test_rejudge_job_applies_release_threshold_override(initialized_db, settings, monkeypatch):
    """改阈值后重判：注入到 config.scoring（保留原 gates），令重判按新阈值判分。"""
    from medeval.config import ThresholdRule
    from server.models_db import ReleaseThresholdConfig

    src_id = _seed_source_run(settings)
    with session_scope() as s:
        s.add(ReleaseThresholdConfig(profile="knowledge", composite_threshold=0.90))
        new = EvalRun(run_slug="(pending)", name="重判阈值", status="pending", parent_run_id=src_id)
        s.add(new)
        s.flush()
        new_id = new.id

    captured: dict = {}

    async def fake_judge(config, cases, per_case_traces, judges, adjudicator, *,
                         progress=None, run_name=None, declare_plan=True, **kw):
        captured["rule"] = config.scoring.profiles["knowledge"].pass_rule
        return make_report(run_name or "rj_2026-06-04_1")

    monkeypatch.setattr("server.eval_job.judge_traces", fake_judge)

    job = build_rejudge_job(
        new_id, source_run_id=src_id, run_name="重判阈值", settings=settings,
    )
    asyncio.run(job(InMemoryProgress()))
    rule = captured["rule"]
    assert isinstance(rule, ThresholdRule)
    assert rule.min_composite == 0.90
    # 安全/合规生死线 gates 保留
    assert rule.gates.get("safety") == "full"
    assert rule.gates.get("compliance") == "full"


def test_rejudge_job_without_override_keeps_config(initialized_db, settings, monkeypatch):
    """未配置阈值覆盖时，重判沿用 config.yaml 原 pass_rule（零行为变化）。"""
    from medeval.config import load_config

    src_id = _seed_source_run(settings)
    with session_scope() as s:
        new = EvalRun(run_slug="(pending)", name="重判默认", status="pending", parent_run_id=src_id)
        s.add(new)
        s.flush()
        new_id = new.id

    captured: dict = {}

    async def fake_judge(config, cases, per_case_traces, judges, adjudicator, *,
                         progress=None, run_name=None, declare_plan=True, **kw):
        captured["rule"] = config.scoring.profiles["knowledge"].pass_rule
        return make_report(run_name or "rj_2026-06-04_1")

    monkeypatch.setattr("server.eval_job.judge_traces", fake_judge)

    job = build_rejudge_job(
        new_id, source_run_id=src_id, run_name="重判默认", settings=settings,
    )
    asyncio.run(job(InMemoryProgress()))
    base = load_config(settings.config_path).scoring.profiles["knowledge"].pass_rule
    assert captured["rule"] == base


def _seed_source_with_case_rows(settings, *, failed: bool) -> int:
    """建源 run + 落 CaseResultRow（端点的 only_release_failed 校验查 DB）。"""
    src_id = _seed_source_run(settings)
    with session_scope() as s:
        s.add(CaseResultRow(run_id=src_id, sample_id="bc_001", scenario="x",
                            level="L3", release_passed=True))
        s.add(CaseResultRow(run_id=src_id, sample_id="bc_002", scenario="x",
                            level="L3", release_passed=not failed))
    return src_id


def test_rejudge_endpoint_only_release_failed_passthrough(client, settings, monkeypatch):
    src_id = _seed_source_with_case_rows(settings, failed=True)
    captured: dict = {}

    def fake_builder(new_id, **kw):
        captured.update(kw)

        async def job(progress):
            return None
        return job

    monkeypatch.setattr("server.routers.runs.build_rejudge_job", fake_builder)
    resp = client.post(f"/api/runs/{src_id}/rejudge", json={"only_release_failed": True})
    assert resp.status_code == 201, resp.text
    assert captured.get("only_release_failed") is True


def test_rejudge_endpoint_400_when_no_failed_cases(client, settings):
    src_id = _seed_source_with_case_rows(settings, failed=False)
    resp = client.post(f"/api/runs/{src_id}/rejudge", json={"only_release_failed": True})
    assert resp.status_code == 400


def test_rejudge_endpoint_resolves_judge_model_id(client, settings, monkeypatch):
    src_id = _seed_source_run(settings)
    with session_scope() as s:
        jm = JudgeModelConfig(name="强判官", provider="openai", model="gpt-4o-mega",
                              base_url="https://api.x/v1", api_key="sk-secret")
        s.add(jm)
        s.flush()
        jm_id = jm.id

    captured: dict = {}

    def fake_builder(new_id, **kw):
        captured.update(kw)

        async def job(progress):
            return None
        return job

    monkeypatch.setattr("server.routers.runs.build_rejudge_job", fake_builder)
    resp = client.post(f"/api/runs/{src_id}/rejudge", json={"judge_model_id": jm_id})
    assert resp.status_code == 201, resp.text
    ov = captured.get("judge_override") or {}
    assert ov.get("model") == "gpt-4o-mega"
    assert ov.get("api_key") == "sk-secret"


def test_rejudge_endpoint_404_on_missing_judge_model(client, settings):
    src_id = _seed_source_run(settings)
    resp = client.post(f"/api/runs/{src_id}/rejudge", json={"judge_model_id": 99999})
    assert resp.status_code == 404


def test_rejudge_endpoint_passes_cases_benchmark_id(client, settings, monkeypatch):
    src_id = _seed_source_run(settings)
    # 建一个真实 benchmark 供 cases_benchmark_id 指向（需存在以过 400 校验）
    up = client.post(
        "/api/benchmarks",
        files={"file": ("c.yaml", VALID_YAML_TEXT, "application/x-yaml")},
        data={"name": "rj-bm", "description": ""},
    )
    bm_id = up.json()["id"]
    captured: dict = {}

    def fake_builder(new_id, **kw):
        captured.update(kw)

        async def job(progress):
            return None
        return job

    monkeypatch.setattr("server.routers.runs.build_rejudge_job", fake_builder)
    resp = client.post(
        f"/api/runs/{src_id}/rejudge", json={"cases_benchmark_id": bm_id})
    assert resp.status_code == 201, resp.text
    assert captured.get("cases_benchmark_id") == bm_id
