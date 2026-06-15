"""落盘 / 续跑 / 离线重判 端到端单测（change 2026-06-04-persist-traces-rejudge）。

覆盖：
  - run_traces + out_dir → traces.jsonl.gz 落定；evaluate 不传 out_dir 时不落盘
  - judge_traces：对冻结 trace 重判，与原 run 综合分一致（rejudge 内核）
  - resume：命中成功留痕不再调 adapter、缺失者重跑；adapter 指纹不一致拒绝
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from medeval import trace_store
from medeval.adapter.base import BaseAdapter, ChatResponse
from medeval.config import parse_config
from medeval.models import Level, RunReport, TestCase, Turn
from medeval.service import (
    build_judges,
    evaluate,
    judge_traces,
    run_traces,
)


class _CountingAdapter(BaseAdapter):
    name = "counting"

    def __init__(self):
        self.calls: list[str] = []

    async def chat(self, req) -> ChatResponse:
        # 记录被调用的 user 内容，便于断言哪些 case 真的调了 adapter
        last_user = [m for m in req.messages if m["role"] == "user"][-1]["content"]
        self.calls.append(last_user)
        return ChatResponse(
            reply="建议尽快就医，若情况严重请立即拨打 120。本回答仅供参考，不能替代医生面诊。",
            raw={"x": 1},
        )

    async def close(self):
        pass


def _config(**run_over):
    run = {"name": "persist_test", "concurrency": 2, "timeout_s": 5, "retry": 0}
    run.update(run_over)
    return parse_config(
        {
            "run": run,
            "adapter": {
                "type": "openai_compat",
                "openai_compat": {"base_url": "http://x", "model": "m", "system_prompt": "p"},
            },
            "judges": {
                "hard_gates": {"enabled": True},
                "rule": {"enabled": True},
                "llm": {"enabled": False},
            },
        }
    )


def _cases():
    return [
        TestCase(sample_id=f"c{i}", scenario="s", level=Level.L2, turns=[Turn(content=f"q{i}")])
        for i in range(3)
    ]


# --- 落盘 ------------------------------------------------------------------


def test_evaluate_with_outdir_persists_traces(tmp_path: Path):
    config = _config()
    cases = _cases()
    judges = build_judges(config.judges)
    out_dir = tmp_path / "outputs" / "run1"
    asyncio.run(
        evaluate(config, cases, _CountingAdapter(), judges, None, run_name="run1", out_dir=out_dir)
    )
    gz = out_dir / trace_store.TRACES_GZ
    assert gz.exists()
    bundle = trace_store.read_traces(out_dir)
    assert set(k[0] for k in bundle.by_key) == {"c0", "c1", "c2"}


def test_evaluate_without_outdir_no_traces(tmp_path: Path):
    config = _config()
    cases = _cases()
    judges = build_judges(config.judges)
    report = asyncio.run(evaluate(config, cases, _CountingAdapter(), judges, None))
    assert isinstance(report, RunReport)
    # 未传 out_dir → 不应落任何 trace 文件（行为同现状）
    assert not list(tmp_path.rglob("traces.jsonl.gz"))


# --- 离线重判（judge_traces 内核一致性）------------------------------------


def test_judge_traces_reproduces_scores(tmp_path: Path):
    config = _config()
    cases = _cases()
    judges = build_judges(config.judges)
    # 先正常评测并落盘
    out_dir = tmp_path / "outputs" / "run1"
    report_a = asyncio.run(
        evaluate(config, cases, _CountingAdapter(), judges, None, run_name="run1", out_dir=out_dir)
    )

    # 从落盘 trace 离线重判（零 adapter）
    bundle = trace_store.read_traces(out_dir)
    per_case = bundle.per_case_traces(cases, config.run.repeat)
    judges2 = build_judges(config.judges)
    report_b = asyncio.run(
        judge_traces(config, cases, per_case, judges2, None, run_name="rejudge1")
    )

    a = {r.case.sample_id: r.composite_score for r in report_a.results}
    b = {r.case.sample_id: r.composite_score for r in report_b.results}
    assert a == b
    # verdict 名集合一致
    va = {(r.case.sample_id, tuple(sorted(v.name for v in r.verdicts))) for r in report_a.results}
    vb = {(r.case.sample_id, tuple(sorted(v.name for v in r.verdicts))) for r in report_b.results}
    assert va == vb


# --- 断点续跑 --------------------------------------------------------------


def test_resume_reuses_successful_traces(tmp_path: Path):
    config = _config()
    cases = _cases()
    judges = build_judges(config.judges)

    # 第一次：只为 c0、c1 造成功留痕（模拟 c2 失败/缺失）
    prev_dir = tmp_path / "outputs" / "prev"
    prev_dir.mkdir(parents=True)
    fp = trace_store.adapter_fingerprint(config.adapter.type, config.adapter.model_dump())
    partial_cases = cases[:2]
    per_case = [
        [
            trace_store.ConversationTrace(
                messages=[
                    trace_store.ChatMessage(role="user", content=f"q{i}"),
                    trace_store.ChatMessage(role="assistant", content="建议就医，仅供参考"),
                ],
                error=None,
            )
        ]
        for i in range(2)
    ]
    meta = {
        "schema": trace_store.SCHEMA_VERSION,
        "adapter_fingerprint": fp,
        "store_raw": "on_error",
        "n_runs": 1,
        "n_cases": 2,
    }
    trace_store.write_traces(prev_dir, partial_cases, per_case, store_raw="on_error", meta=meta)

    # 续跑：c0/c1 复用（不调 adapter），c2 重跑
    adapter = _CountingAdapter()
    out_dir = tmp_path / "outputs" / "resumed"
    asyncio.run(
        evaluate(
            config, cases, adapter, build_judges(config.judges), None,
            run_name="resumed", out_dir=out_dir, resume_dir=prev_dir,
        )
    )
    # 只有 c2 真正调用了 adapter
    assert adapter.calls == ["q2"]
    # 新目录留痕齐全
    bundle = trace_store.read_traces(out_dir)
    assert set(k[0] for k in bundle.by_key) == {"c0", "c1", "c2"}


def test_resume_rejects_fingerprint_mismatch(tmp_path: Path):
    config = _config()
    cases = _cases()
    prev_dir = tmp_path / "outputs" / "prev"
    prev_dir.mkdir(parents=True)
    meta = {
        "schema": trace_store.SCHEMA_VERSION,
        "adapter_fingerprint": "DIFFERENT",
        "store_raw": "on_error",
        "n_runs": 1,
        "n_cases": 1,
    }
    trace_store.write_traces(
        prev_dir, cases[:1],
        [[trace_store.ConversationTrace(messages=[], error=None)]],
        store_raw="on_error", meta=meta,
    )
    with pytest.raises(Exception):
        asyncio.run(
            evaluate(
                config, cases, _CountingAdapter(), build_judges(config.judges), None,
                run_name="r", out_dir=tmp_path / "o", resume_dir=prev_dir,
            )
        )
