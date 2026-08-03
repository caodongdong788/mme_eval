"""Pairwise 对比后端测试（OpenSpec change add-pairwise-comparison）。

覆盖：可比性校验各拒绝分支、后台逐题落库 + 汇总（monkeypatch comparator 不触网）、
接口 422/201。
"""

from __future__ import annotations

import asyncio

import pytest

from server.compare import check_pairwise_comparable, pairwise_subject_diff
from server.db import get_sessionmaker
from server.models_db import (
    Benchmark,
    CaseResultRow,
    EvalRun,
    JudgeModelConfig,
    PairwiseCaseVerdict,
    PairwiseComparison,
)
from factories import make_case_result


def _mk_run(
    session,
    *,
    name: str,
    benchmark_id: int = 1,
    fingerprints: dict | None = None,
    has_traces: bool = True,
    adapter_overrides: dict | None = None,
) -> EvalRun:
    run = EvalRun(
        run_slug=name,
        name=name,
        status="success",
        benchmark_id=benchmark_id,
        has_traces=has_traces,
        judge_fingerprints=fingerprints if fingerprints is not None else {"dimension": "x"},
        config_snapshot={},
        adapter_overrides=adapter_overrides or {},
    )
    session.add(run)
    session.flush()
    return run


def _mk_cases(
    session,
    run_id: int,
    sample_ids: list[str],
    *,
    rag_statuses: dict[str, str] | None = None,
) -> None:
    for sid in sample_ids:
        cr = make_case_result(sid)
        session.add(
            CaseResultRow(
                run_id=run_id,
                sample_id=sid,
                release_passed=cr.release_passed,
                rag_status=(rag_statuses or {}).get(sid, "unknown"),
                detail_json=cr.model_dump(mode="json"),
            )
        )
    session.flush()


# ---------------------------------------------------------------------------
# 可比性校验


def test_comparable_ok(session):
    a = _mk_run(session, name="A")
    b = _mk_run(session, name="B", adapter_overrides={"system_prompt": "改过的"})
    _mk_cases(session, a.id, ["s1", "s2"])
    _mk_cases(session, b.id, ["s1", "s2"])
    session.commit()
    assert check_pairwise_comparable(session, a, b) == []
    # 被测 prompt 不同允许，并体现在 subject_diff
    diff = pairwise_subject_diff(a, b)
    assert "system_prompt" in diff


def test_pairwise_precheck_reports_actual_rag_candidates(client, session):
    a = _mk_run(session, name="A", adapter_overrides={"enable_rag": False})
    b = _mk_run(session, name="B", adapter_overrides={"enable_rag": True})
    statuses_a = {sid: "not_triggered" for sid in ("s1", "s2", "s3", "s4")}
    statuses_b = {
        "s1": "hit",
        "s2": "not_triggered",
        "s3": "unknown",
        "s4": "miss",
    }
    _mk_cases(session, a.id, list(statuses_a), rag_statuses=statuses_a)
    _mk_cases(session, b.id, list(statuses_b), rag_statuses=statuses_b)
    session.commit()

    body = client.get(
        "/api/compare/pairwise/precheck",
        params={"run_a_id": a.id, "run_b_id": b.id},
    ).json()

    assert body["comparable"] is True
    assert body["subject_diff"]["enable_rag"] == {"a": False, "b": True}
    assert body["rag_analysis"]["common_cases"] == 4
    assert body["rag_analysis"]["selected_cases"] == 2
    assert body["rag_analysis"]["excluded_cases"] == 2
    assert body["rag_analysis"]["unknown_cases"] == 1
    assert body["rag_analysis"]["rag_side"] == "B"
    assert body["rag_analysis"]["baseline_triggered_cases"] == 0


def test_incomparable_different_benchmark(session):
    a = _mk_run(session, name="A", benchmark_id=1)
    b = _mk_run(session, name="B", benchmark_id=2)
    _mk_cases(session, a.id, ["s1"])
    _mk_cases(session, b.id, ["s1"])
    session.commit()
    reasons = check_pairwise_comparable(session, a, b)
    assert any("benchmark" in r for r in reasons)


def test_incomparable_different_fingerprint(session):
    a = _mk_run(
        session,
        name="A",
        fingerprints={"dimension": "aaaa1111", "guideline": "same000"},
    )
    b = _mk_run(
        session,
        name="B",
        fingerprints={"dimension": "bbbb2222", "guideline": "same000"},
    )
    _mk_cases(session, a.id, ["s1"])
    _mk_cases(session, b.id, ["s1"])
    session.commit()
    reasons = check_pairwise_comparable(session, a, b)
    blob = "；".join(reasons)
    # 必须点名「具体哪个判官」不同，且用大白话（不暴露哈希指纹）
    assert "八维评分" in blob
    assert "aaaa1111" not in blob and "bbbb2222" not in blob
    # 相同的指南判官不应被列入差异
    assert "指南覆盖评分" not in blob


def test_incomparable_different_sample_set(session):
    a = _mk_run(session, name="A")
    b = _mk_run(session, name="B")
    _mk_cases(session, a.id, ["s1", "s2"])
    _mk_cases(session, b.id, ["s1", "s3"])
    session.commit()
    reasons = check_pairwise_comparable(session, a, b)
    assert any("用例集合" in r for r in reasons)


def test_incomparable_missing_traces(session):
    a = _mk_run(session, name="A", has_traces=True)
    b = _mk_run(session, name="B", has_traces=False)
    _mk_cases(session, a.id, ["s1"])
    _mk_cases(session, b.id, ["s1"])
    session.commit()
    reasons = check_pairwise_comparable(session, a, b)
    assert any("留痕" in r for r in reasons)


# ---------------------------------------------------------------------------
# 后台执行 + 汇总（monkeypatch comparator）


class _FakeComparator:
    def fingerprint(self) -> str:
        return "fp_fake"

    async def compare_case(self, case, trace_a, trace_b):
        from medeval.pairwise import PairwiseResult

        # s1→B 更好；s2→A 更好（回退）；其余 tie
        if case.sample_id == "s1":
            return PairwiseResult(
                winner="B", confidence="high", swap_consistent=True,
                dimension_winners={"professional_accuracy": "B"}, reason="B 更准",
            )
        if case.sample_id == "s2":
            return PairwiseResult(
                winner="A", confidence="high", swap_consistent=True,
                dimension_winners={"communication": "A"}, reason="B 啰嗦",
            )
        return PairwiseResult(winner="tie", confidence="low")


def test_run_pairwise_comparison_aggregates(session, monkeypatch):
    from server import pairwise_job

    a = _mk_run(session, name="A")
    b = _mk_run(session, name="B")
    _mk_cases(session, a.id, ["s1", "s2", "s3"])
    _mk_cases(session, b.id, ["s1", "s2", "s3"])
    comp = PairwiseComparison(run_a_id=a.id, run_b_id=b.id, judge_model="m", status="running")
    session.add(comp)
    session.flush()
    comp_id = comp.id
    session.commit()

    monkeypatch.setattr(
        pairwise_job, "_build_comparator", lambda _id: (_FakeComparator(), "m", 4)
    )
    asyncio.run(pairwise_job.run_pairwise_comparison(comp_id, judge_model_id=999))

    maker = get_sessionmaker()
    s2 = maker()
    try:
        comp = s2.get(PairwiseComparison, comp_id)
        assert comp.status == "done"
        assert comp.judge_fingerprint == "fp_fake"
        summary = comp.summary
        assert summary["b_wins"] == 1
        assert summary["a_wins"] == 1
        assert summary["ties"] == 1
        assert summary["total"] == 3
        assert summary["regressions"] == ["s2"]
        assert summary["improvements"] == ["s1"]
        verdicts = s2.execute(
            __import__("sqlalchemy").select(PairwiseCaseVerdict).where(
                PairwiseCaseVerdict.comparison_id == comp_id
            )
        ).scalars().all()
        assert len(verdicts) == 3
    finally:
        s2.close()


def test_run_pairwise_only_compares_cases_where_b_really_triggered_rag(
    session, monkeypatch
):
    from server import pairwise_job

    sample_ids = ["s1", "s2", "s3", "s4"]
    a = _mk_run(session, name="A", adapter_overrides={"enable_rag": False})
    b = _mk_run(session, name="B", adapter_overrides={"enable_rag": True})
    _mk_cases(
        session,
        a.id,
        sample_ids,
        rag_statuses={sid: "not_triggered" for sid in sample_ids},
    )
    _mk_cases(
        session,
        b.id,
        sample_ids,
        rag_statuses={
            "s1": "hit",
            "s2": "not_triggered",
            "s3": "unknown",
            "s4": "failed",
        },
    )
    comp = PairwiseComparison(
        run_a_id=a.id,
        run_b_id=b.id,
        judge_model="m",
        status="running",
        scope="rag_triggered_only",
    )
    session.add(comp)
    session.flush()
    comp_id = comp.id
    session.commit()

    monkeypatch.setattr(
        pairwise_job, "_build_comparator", lambda _id: (_FakeComparator(), "m", 4)
    )
    asyncio.run(pairwise_job.run_pairwise_comparison(comp_id, judge_model_id=999))

    maker = get_sessionmaker()
    s2 = maker()
    try:
        saved = s2.get(PairwiseComparison, comp_id)
        assert saved.status == "done"
        assert saved.total_cases == 2
        assert saved.done_cases == 2
        assert saved.summary["total"] == 2
        assert saved.summary["rag_scope"] == {
            "rag_side": "B",
            "common_cases": 4,
            "selected_cases": 2,
            "excluded_cases": 2,
            "unknown_cases": 1,
            "rag_status_counts": {
                "hit": 1,
                "not_triggered": 1,
                "unknown": 1,
                "failed": 1,
            },
        }
        verdict_ids = set(
            s2.execute(
                __import__("sqlalchemy").select(PairwiseCaseVerdict.sample_id).where(
                    PairwiseCaseVerdict.comparison_id == comp_id
                )
            ).scalars()
        )
        assert verdict_ids == {"s1", "s4"}
    finally:
        s2.close()


def test_run_pairwise_auto_detects_a_as_rag_side(session, monkeypatch):
    from server import pairwise_job

    a = _mk_run(session, name="A-rag", adapter_overrides={"enable_rag": True})
    b = _mk_run(session, name="B-no-rag", adapter_overrides={"enable_rag": False})
    _mk_cases(
        session,
        a.id,
        ["s1", "s2"],
        rag_statuses={"s1": "hit", "s2": "not_triggered"},
    )
    _mk_cases(
        session,
        b.id,
        ["s1", "s2"],
        rag_statuses={"s1": "not_triggered", "s2": "not_triggered"},
    )
    comp = PairwiseComparison(
        run_a_id=a.id,
        run_b_id=b.id,
        judge_model="m",
        status="running",
        scope="rag_triggered_only",
    )
    session.add(comp)
    session.flush()
    comp_id = comp.id
    session.commit()

    monkeypatch.setattr(
        pairwise_job, "_build_comparator", lambda _id: (_FakeComparator(), "m", 4)
    )
    asyncio.run(pairwise_job.run_pairwise_comparison(comp_id, judge_model_id=999))

    maker = get_sessionmaker()
    s2 = maker()
    try:
        saved = s2.get(PairwiseComparison, comp_id)
        assert saved.status == "done"
        assert saved.total_cases == 1
        assert saved.summary["rag_scope"]["rag_side"] == "A"
        verdict_ids = set(
            s2.execute(
                __import__("sqlalchemy").select(PairwiseCaseVerdict.sample_id).where(
                    PairwiseCaseVerdict.comparison_id == comp_id
                )
            ).scalars()
        )
        assert verdict_ids == {"s1"}
    finally:
        s2.close()


# ---------------------------------------------------------------------------
# 接口 422 / 201


def test_create_pairwise_422_incomparable(client, session):
    a = _mk_run(session, name="A", fingerprints={"j": "x"})
    b = _mk_run(session, name="B", fingerprints={"j": "y"})
    _mk_cases(session, a.id, ["s1"])
    _mk_cases(session, b.id, ["s1"])
    jm = JudgeModelConfig(name="judge1", provider="openai", model="gpt-4o-mini")
    session.add(jm)
    session.flush()
    session.commit()
    resp = client.post(
        "/api/compare/pairwise",
        json={"run_a_id": a.id, "run_b_id": b.id, "judge_model_id": jm.id},
    )
    assert resp.status_code == 422


def test_create_pairwise_201(client, session, monkeypatch):
    from server.routers import compare as compare_router

    async def _noop(comparison_id, judge_model_id):
        return None

    monkeypatch.setattr(compare_router, "run_pairwise_comparison", _noop)

    a = _mk_run(session, name="A")
    b = _mk_run(session, name="B")
    _mk_cases(session, a.id, ["s1"])
    _mk_cases(session, b.id, ["s1"])
    jm = JudgeModelConfig(name="judge1", provider="openai", model="gpt-4o-mini")
    session.add(jm)
    session.flush()
    session.commit()
    resp = client.post(
        "/api/compare/pairwise",
        json={"run_a_id": a.id, "run_b_id": b.id, "judge_model_id": jm.id},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "running"
    assert body["run_a_id"] == a.id


def test_create_rag_scoped_pairwise_rejects_when_b_has_no_real_calls(
    client, session
):
    a = _mk_run(session, name="A", adapter_overrides={"enable_rag": False})
    b = _mk_run(session, name="B", adapter_overrides={"enable_rag": True})
    _mk_cases(session, a.id, ["s1"], rag_statuses={"s1": "not_triggered"})
    _mk_cases(session, b.id, ["s1"], rag_statuses={"s1": "unknown"})
    jm = JudgeModelConfig(name="judge-rag-empty", provider="openai", model="judge")
    session.add(jm)
    session.commit()

    response = client.post(
        "/api/compare/pairwise",
        json={
            "run_a_id": a.id,
            "run_b_id": b.id,
            "judge_model_id": jm.id,
            "scope": "rag_triggered_only",
        },
    )

    assert response.status_code == 422
    assert "没有检测到真实 RAG 调用" in response.text


def test_pairwise_detail_includes_performance_and_token_observability(client, session):
    a = _mk_run(session, name="A")
    b = _mk_run(session, name="B")
    a.latency_summary = {"avg_ms": 1200, "p90_ms": 1800}
    a.ttft_summary = {"avg_ms": 300, "p90_ms": 450}
    a.token_summary = {"total_tokens": 1000, "avg_tokens_per_run": 500}
    b.latency_summary = {"avg_ms": 900, "p90_ms": 1500}
    b.ttft_summary = {"avg_ms": 200, "p90_ms": 350}
    b.token_summary = {"total_tokens": 1400, "avg_tokens_per_run": 700}
    _mk_cases(session, a.id, ["s1"], rag_statuses={"s1": "not_triggered"})
    _mk_cases(session, b.id, ["s1"], rag_statuses={"s1": "hit"})
    comp = PairwiseComparison(run_a_id=a.id, run_b_id=b.id, judge_model="m", status="done")
    session.add(comp)
    session.flush()
    session.add(PairwiseCaseVerdict(comparison_id=comp.id, sample_id="s1"))
    session.commit()

    body = client.get(f"/api/compare/pairwise/{comp.id}").json()
    assert body["run_a_observability"] == {
        "latency_summary": {"avg_ms": 1200, "p90_ms": 1800},
        "ttft_summary": {"avg_ms": 300, "p90_ms": 450},
        "token_summary": {"total_tokens": 1000, "avg_tokens_per_run": 500},
    }
    assert body["run_b_observability"]["latency_summary"]["avg_ms"] == 900
    assert body["run_b_observability"]["ttft_summary"]["avg_ms"] == 200
    assert body["run_b_observability"]["token_summary"]["total_tokens"] == 1400
    assert body["verdicts"][0]["rag_status_a"] == "not_triggered"
    assert body["verdicts"][0]["rag_status_b"] == "hit"


def test_rag_scoped_pairwise_observability_only_uses_selected_cases(client, session):
    a = _mk_run(session, name="A")
    b = _mk_run(session, name="B")
    _mk_cases(session, a.id, ["s1", "s2"], rag_statuses={"s1": "not_triggered", "s2": "not_triggered"})
    _mk_cases(session, b.id, ["s1", "s2"], rag_statuses={"s1": "hit", "s2": "not_triggered"})
    rows = session.execute(
        __import__("sqlalchemy").select(CaseResultRow).where(
            CaseResultRow.run_id.in_([a.id, b.id])
        )
    ).scalars().all()
    for row in rows:
        row.latency_ms = 1000 if row.sample_id == "s1" else 9999
        row.ttft_ms = 250 if row.sample_id == "s1" else 9999
        row.total_tokens = 100 if row.sample_id == "s1" else 999
    comp = PairwiseComparison(
        run_a_id=a.id,
        run_b_id=b.id,
        judge_model="m",
        status="done",
        scope="rag_triggered_only",
    )
    session.add(comp)
    session.flush()
    session.add(PairwiseCaseVerdict(comparison_id=comp.id, sample_id="s1"))
    session.commit()

    body = client.get(f"/api/compare/pairwise/{comp.id}").json()

    assert body["run_a_observability"]["latency_summary"]["avg_ms"] == 1000
    assert body["run_b_observability"]["latency_summary"]["p90_ms"] == 1000
    assert body["run_a_observability"]["ttft_summary"]["avg_ms"] == 250
    assert body["run_b_observability"]["ttft_summary"]["p90_ms"] == 250
    assert body["run_a_observability"]["token_summary"]["total_tokens"] == 100
    assert body["run_b_observability"]["token_summary"]["avg_tokens_per_run"] == 100


def test_pairwise_default_judge_falls_back_to_llm_api_key_env(session, monkeypatch):
    """默认判分模型不落库密钥时，也必须和常规评测使用同一个环境变量。"""
    from server import pairwise_job

    captured: dict = {}

    class _CaptureComparator:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("medeval.pairwise.PairwiseComparator", _CaptureComparator)
    model = JudgeModelConfig(
        name="默认环境变量判官",
        provider="openai",
        model="kimi-k2.6",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=None,
    )
    session.add(model)
    session.commit()

    comparator, label, concurrency = pairwise_job._build_comparator(model.id)

    assert isinstance(comparator, _CaptureComparator)
    assert label == "kimi-k2.6"
    assert concurrency == 4
    assert captured["api_key"] == ""
    assert captured["api_key_env"] == "LLM_API_KEY"


def test_pairwise_note_create_patch_delete(client, session, monkeypatch):
    from server.routers import compare as compare_router

    async def _noop(comparison_id, judge_model_id):
        return None

    monkeypatch.setattr(compare_router, "run_pairwise_comparison", _noop)

    a = _mk_run(session, name="A")
    b = _mk_run(session, name="B")
    _mk_cases(session, a.id, ["s1"])
    _mk_cases(session, b.id, ["s1"])
    jm = JudgeModelConfig(name="judge1", provider="openai", model="gpt-4o-mini")
    session.add(jm)
    session.flush()
    session.commit()

    # 发起带备注 → 回显
    resp = client.post(
        "/api/compare/pairwise",
        json={
            "run_a_id": a.id,
            "run_b_id": b.id,
            "judge_model_id": jm.id,
            "note": "  验证 v6 收紧后安全是否退化  ",
        },
    )
    assert resp.status_code == 201, resp.text
    cid = resp.json()["id"]
    assert resp.json()["note"] == "验证 v6 收紧后安全是否退化"  # 已 strip

    # 列表回显 note
    listed = client.get("/api/compare/pairwise").json()
    assert next(r for r in listed if r["id"] == cid)["note"] == "验证 v6 收紧后安全是否退化"

    # 给该对比塞一条 verdict，验证删除级联
    with get_sessionmaker()() as s:
        s.add(PairwiseCaseVerdict(comparison_id=cid, sample_id="s1", winner="B"))
        s.commit()

    # 二次编辑 note：仅改 note
    upd = client.patch(f"/api/compare/pairwise/{cid}", json={"note": "改成新的目的"})
    assert upd.status_code == 200, upd.text
    assert upd.json()["note"] == "改成新的目的"
    assert upd.json()["run_a_id"] == a.id  # 其余字段不变

    # 删除 → 204，连带 verdict 清空，再查 404
    assert client.delete(f"/api/compare/pairwise/{cid}").status_code == 204
    assert client.get(f"/api/compare/pairwise/{cid}").status_code == 404
    with get_sessionmaker()() as s:
        from sqlalchemy import select

        left = s.execute(
            select(PairwiseCaseVerdict).where(PairwiseCaseVerdict.comparison_id == cid)
        ).scalars().all()
        assert left == []


def test_pairwise_patch_delete_404(client, session):
    assert client.patch("/api/compare/pairwise/99999", json={"note": "x"}).status_code == 404
    assert client.delete("/api/compare/pairwise/99999").status_code == 404


def test_pairwise_human_calibration_recomputes_summary(client, session):
    a = _mk_run(session, name="A")
    b = _mk_run(session, name="B")
    comp = PairwiseComparison(
        run_a_id=a.id,
        run_b_id=b.id,
        judge_model="m",
        status="done",
        summary={
            "total": 2,
            "a_wins": 0,
            "b_wins": 0,
            "ties": 2,
            "overall_winner": "tie",
            "regressions": [],
            "improvements": [],
        },
    )
    session.add(comp)
    session.flush()
    session.add(
        PairwiseCaseVerdict(
            comparison_id=comp.id,
            sample_id="s1",
            winner="tie",
            confidence="low",
            swap_consistent=False,
            reason="机器持平",
        )
    )
    session.add(
        PairwiseCaseVerdict(
            comparison_id=comp.id,
            sample_id="s2",
            winner="tie",
            confidence="high",
            swap_consistent=True,
            reason="真平",
        )
    )
    session.commit()
    cid = comp.id

    resp = client.patch(
        f"/api/compare/pairwise/{cid}/cases/s1",
        json={
            "winner": "B",
            "dimension_winners": {
                "medical_safety": "B",
                "plan_feasibility": "B",
                "communication": "tie",
            },
            "reason": "人工认定 B 更完整",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["winner"] == "B"
    assert body["confidence_kind"] == "human"
    assert body["human_calibrated"] is True
    assert body["auto_winner"] == "tie"

    invalid = client.patch(
        f"/api/compare/pairwise/{cid}/cases/s1",
        json={"winner": "A", "dimension_winners": {"safety": "A"}},
    )
    assert invalid.status_code == 422

    detail = client.get(f"/api/compare/pairwise/{cid}").json()
    assert detail["summary"]["b_wins"] == 1
    assert detail["summary"]["ties"] == 1
    assert detail["summary"]["human_calibrated_count"] == 1
    assert detail["summary"]["overall_winner"] == "B"

    reset = client.delete(f"/api/compare/pairwise/{cid}/cases/s1")
    assert reset.status_code == 200, reset.text
    assert reset.json()["confidence_kind"] == "order"
    assert reset.json()["human_calibrated"] is False
    detail2 = client.get(f"/api/compare/pairwise/{cid}").json()
    assert detail2["summary"]["b_wins"] == 0
    assert detail2["summary"]["ties"] == 2
