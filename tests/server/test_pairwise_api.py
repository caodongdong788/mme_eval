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
    scoring: dict | None = None,
    has_traces: bool = True,
    adapter_overrides: dict | None = None,
) -> EvalRun:
    run = EvalRun(
        run_slug=name,
        name=name,
        status="success",
        benchmark_id=benchmark_id,
        has_traces=has_traces,
        judge_fingerprints=fingerprints if fingerprints is not None else {"hard_gate": "x"},
        config_snapshot={"scoring": scoring if scoring is not None else {"safety": 0.3}},
        adapter_overrides=adapter_overrides or {},
    )
    session.add(run)
    session.flush()
    return run


def _mk_cases(session, run_id: int, sample_ids: list[str]) -> None:
    for sid in sample_ids:
        cr = make_case_result(sid)
        session.add(
            CaseResultRow(
                run_id=run_id,
                sample_id=sid,
                release_passed=cr.release_passed,
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
        fingerprints={"hard_gate": "aaaa1111", "rule": "same000", "llm": "llmAAAA0"},
    )
    b = _mk_run(
        session,
        name="B",
        fingerprints={"hard_gate": "bbbb2222", "rule": "same000", "llm": "llmBBBB0"},
    )
    _mk_cases(session, a.id, ["s1"])
    _mk_cases(session, b.id, ["s1"])
    session.commit()
    reasons = check_pairwise_comparable(session, a, b)
    blob = "；".join(reasons)
    # 必须点名「具体哪个判官」不同，且用大白话（不暴露哈希指纹）
    assert "HardGate" in blob and "LLM" in blob
    assert "aaaa1111" not in blob and "bbbb2222" not in blob
    # 相同的判官（rule）不应被列入差异
    assert "规则" not in blob


def test_incomparable_different_scoring(session):
    a = _mk_run(session, name="A", scoring={"safety": 0.3, "experience": 0.2})
    b = _mk_run(session, name="B", scoring={"safety": 0.4, "experience": 0.2})
    _mk_cases(session, a.id, ["s1"])
    _mk_cases(session, b.id, ["s1"])
    session.commit()
    reasons = check_pairwise_comparable(session, a, b)
    blob = "；".join(reasons)
    # 指纹相同但算分口径不同：点名差异字段 safety，不点名相同字段 experience
    assert "口径" in blob
    assert "safety" in blob
    assert "experience" not in blob


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
                dimension_winners={"safety": "B"}, reason="B 更准",
            )
        if case.sample_id == "s2":
            return PairwiseResult(
                winner="A", confidence="high", swap_consistent=True,
                dimension_winners={"experience": "A"}, reason="B 啰嗦",
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
            "dimension_winners": {"safety": "B", "function": "B", "experience": "tie"},
            "reason": "人工认定 B 更完整",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["winner"] == "B"
    assert body["confidence_kind"] == "human"
    assert body["human_calibrated"] is True
    assert body["auto_winner"] == "tie"

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
