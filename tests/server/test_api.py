"""REST API 接口测试（FastAPI TestClient）。

发起评测的真实执行通过 stub 避免网络；数据驱动的查询端点用 ingest_report 直接播种 DB。
"""

from __future__ import annotations

from factories import VALID_YAML_TEXT, make_report

from server.benchmarks import ensure_builtin_benchmark
from server.db import session_scope
from server.ingest import ingest_report


def _seed_builtin(settings) -> int:
    with session_scope() as s:
        bm = ensure_builtin_benchmark(s, settings)
        s.flush()
        return bm.id


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_judge_defaults(client, settings):
    resp = client.get("/api/config/judge-defaults")
    assert resp.status_code == 200
    body = resp.json()
    assert {"provider", "model", "base_url", "api_version", "model_options"} <= set(body)
    assert isinstance(body["model_options"], list)


def test_list_and_get_benchmarks(client, settings):
    resp = client.get("/api/benchmarks")
    assert resp.status_code == 200
    data = resp.json()
    assert any(b["source"] == "builtin" for b in data)
    bid = data[0]["id"]
    cases = client.get(f"/api/benchmarks/{bid}/cases")
    assert cases.status_code == 200
    assert len(cases.json()) > 0


def test_upload_benchmark_via_api(client, settings):
    files = {"file": ("mine.yaml", VALID_YAML_TEXT, "application/x-yaml")}
    resp = client.post("/api/benchmarks", data={"name": "上传集"}, files=files)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source"] == "uploaded"
    assert body["case_count"] == 2

    assert set(body["levels"]) == {"L1", "L3"}

    # 非法 YAML 被拒
    bad = {"file": ("bad.yaml", "- sample_id: x\n  scenario: 缺字段", "application/x-yaml")}
    resp2 = client.post("/api/benchmarks", data={"name": "坏的"}, files=bad)
    assert resp2.status_code == 422


def test_download_and_replace_benchmark_via_api(client, settings):
    bid = client.post(
        "/api/benchmarks",
        data={"name": "可改集"},
        files={"file": ("m.yaml", VALID_YAML_TEXT, "application/x-yaml")},
    ).json()["id"]

    dl = client.get(f"/api/benchmarks/{bid}/download")
    assert dl.status_code == 200
    assert "up_001" in dl.text

    new = "- sample_id: rep_1\n  scenario: s\n  level: L2\n  turns:\n    - role: user\n      content: hi"
    rep = client.put(
        f"/api/benchmarks/{bid}", files={"file": ("n.yaml", new, "application/x-yaml")}
    )
    assert rep.status_code == 200
    assert rep.json()["case_count"] == 1
    assert rep.json()["levels"] == ["L2"]


def test_create_run_strips_api_key(client, settings, monkeypatch):
    bid = _seed_builtin(settings)

    async def _noop(progress):
        return None

    monkeypatch.setattr(
        "server.routers.runs.build_eval_job", lambda *a, **k: _noop
    )
    resp = client.post(
        "/api/runs",
        json={
            "benchmark_id": bid,
            "run_name": "t1",
            "judge": {"model": "gpt-4o", "provider": "openai", "api_key": "SECRET"},
        },
    )
    assert resp.status_code == 201, resp.text
    rid = resp.json()["id"]

    detail = client.get(f"/api/runs/{rid}").json()
    assert detail["judge_overrides"]["model"] == "gpt-4o"
    assert "api_key" not in detail["judge_overrides"]


def test_create_run_unknown_benchmark_404(client, settings):
    resp = client.post("/api/runs", json={"benchmark_id": 999999})
    assert resp.status_code == 404


def test_create_run_duplicate_name_rejected(client, settings, monkeypatch):
    bid = _seed_builtin(settings)

    async def _noop(progress):
        return None

    monkeypatch.setattr("server.routers.runs.build_eval_job", lambda *a, **k: _noop)
    first = client.post(
        "/api/runs", json={"benchmark_id": bid, "run_name": "dup-name"}
    )
    assert first.status_code == 201, first.text
    dup = client.post(
        "/api/runs", json={"benchmark_id": bid, "run_name": "dup-name"}
    )
    assert dup.status_code == 409
    assert "名称" in dup.json()["detail"]


def test_delete_completed_run(client, settings):
    bid = _seed_builtin(settings)
    with session_scope() as s:
        a = ingest_report(s, make_report("delrun"), benchmark_id=bid)
        s.flush()
        aid = a.id

    # 用例结果存在
    assert client.get(f"/api/runs/{aid}/cases").status_code == 200
    resp = client.delete(f"/api/runs/{aid}")
    assert resp.status_code == 204, resp.text
    assert client.get(f"/api/runs/{aid}").status_code == 404


def test_delete_run_with_annotations(client, settings):
    """有人审裁定时删除仍须成功（级联清 case_annotation）。"""
    from server.models_db import CaseAnnotation

    bid = _seed_builtin(settings)
    with session_scope() as s:
        run = ingest_report(s, make_report("annotated"), benchmark_id=bid)
        s.flush()
        s.add(
            CaseAnnotation(
                run_id=run.id,
                sample_id="bc_001",
                verdict="agree",
                comment="test",
            )
        )
        s.flush()
        rid = run.id

    assert client.delete(f"/api/runs/{rid}").status_code == 204
    assert client.get(f"/api/runs/{rid}").status_code == 404


def test_delete_missing_run_404(client, settings):
    assert client.delete("/api/runs/424242").status_code == 404


def test_delete_running_run_rejected(client, settings):
    from server.models_db import EvalRun

    with session_scope() as s:
        run = EvalRun(run_slug="(pending)", name="running-one", status="running")
        s.add(run)
        s.flush()
        rid = run.id
    resp = client.delete(f"/api/runs/{rid}")
    assert resp.status_code == 400


def test_seeded_run_queries(client, settings):
    bid = _seed_builtin(settings)
    with session_scope() as s:
        a = ingest_report(s, make_report("runA"), benchmark_id=bid)
        b = ingest_report(s, make_report("runB"), benchmark_id=bid)
        s.flush()
        aid, bid2 = a.id, b.id

    # 用例结果列表 + 筛选
    rows = client.get(f"/api/runs/{aid}/cases").json()
    assert len(rows) == 2
    failed = client.get(f"/api/runs/{aid}/cases", params={"release_passed": "false"}).json()
    assert [r["sample_id"] for r in failed] == ["bc_002"]

    # 用例明细
    detail = client.get(f"/api/runs/{aid}/cases/bc_002").json()
    assert detail["case"]["sample_id"] == "bc_002"
    assert detail["release_passed"] is False

    # 两次 run 对比
    diff = client.get(f"/api/runs/{aid}/diff", params={"against": bid2}).json()
    assert diff["pass_rate_delta"] == 0.0
    assert diff["regressions"] == []

    # 趋势
    trends = client.get("/api/dashboard/trends", params={"benchmark_id": bid}).json()
    assert len(trends["points"]) == 2
    assert trends["points"][0]["pass_rate"] == 0.5


def test_export_transcripts(client, settings, monkeypatch):
    bid = _seed_builtin(settings)
    with session_scope() as s:
        a = ingest_report(s, make_report("exprun"), benchmark_id=bid)
        s.flush()
        aid = a.id

    captured: dict = {}

    def _fake_publish(xlsx_path, *, parent_folder_token, title):
        captured["token"] = parent_folder_token
        return "https://feishu.example/sheet/abc"

    monkeypatch.setattr(
        "server.services.case_export.publish_xlsx_to_lark", _fake_publish
    )
    resp = client.post(f"/api/runs/{aid}/export-transcripts")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["url"].startswith("https://feishu")
    assert body["count"] == 2

    # 用户动态传入 token → 透传给飞书发布
    resp2 = client.post(
        f"/api/runs/{aid}/export-transcripts",
        params={"parent_folder_token": "fld_user_xyz"},
    )
    assert resp2.status_code == 200, resp2.text
    assert captured["token"] == "fld_user_xyz"

    # 传空串 → 上传到个人根目录（token 为空）
    resp3 = client.post(
        f"/api/runs/{aid}/export-transcripts",
        params={"parent_folder_token": ""},
    )
    assert resp3.status_code == 200, resp3.text
    assert captured["token"] == ""

    # 过滤后无用例 → 400
    empty = client.post(f"/api/runs/{aid}/export-transcripts", params={"level": "L4"})
    assert empty.status_code == 400
