"""成本 / Token 观测指标单测。

覆盖 OpenSpec change add-token-cost-observability 的核心场景：
  - _extract_token_usage 归一化 + 认不出安全降级
  - runner 当场采集 token；store_raw=on_error 裁剪后仍在
  - token 字段不影响判分
  - N=3 时 per_run_tokens 长度为 3；token_summary 含总 token / 平均
  - 错误 run 不计入聚合
  - 配置单价→出 cost；未配置→cost N/A
  - diff 在历史报告缺 token_summary 时友好降级
  - 历史无 token 字段的 report.json 仍可反序列化
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse
from medeval.judges import HardGateJudge, RuleJudge, judge_all
from medeval.models import (
    CaseResult,
    ChatMessage,
    ConversationTrace,
    Level,
    RunReport,
    TestCase,
    Turn,
)
from medeval.reporter import build_report, diff_runs
from medeval.reporter.markdown_report import render_markdown
from medeval.runner import (
    _extract_token_usage,
    fold_n_runs,
    run_cases,
    trace_total_tokens,
)
from medeval.runner.executor import _run_one
from medeval.trace_store import trim_raw_responses


class _UsageAdapter(BaseAdapter):
    """每轮返回固定 usage 的 stub。"""

    name = "stub"

    def __init__(self, prompt: int = 10, completion: int = 5):
        self.n = 0
        self.prompt = prompt
        self.completion = completion

    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.n += 1
        return ChatResponse(
            reply=f"reply-{self.n}",
            raw={
                "usage": {
                    "prompt_tokens": self.prompt,
                    "completion_tokens": self.completion,
                    "total_tokens": self.prompt + self.completion,
                }
            },
        )

    async def close(self) -> None:
        pass


def _case(sid: str = "a", turns: int = 1) -> TestCase:
    return TestCase(
        sample_id=sid,
        scenario="t",
        level=Level.L2,
        turns=[Turn(role="user", content=f"q{i}") for i in range(turns)],
    )


def _result(passed: bool, tokens: int, error: str | None = None) -> CaseResult:
    trace = ConversationTrace(
        messages=[ChatMessage(role="assistant", content="x")],
        turn_token_usage=[
            {"prompt_tokens": tokens, "completion_tokens": 0, "total_tokens": tokens}
        ]
        if tokens
        else [],
        error=error,
    )
    return CaseResult(
        case=_case(),
        trace=trace,
        verdicts=[],
        hard_gate_passed=passed,
        gate_passed=passed,
        per_run_tokens=[tokens] if not error else [tokens],
    )


# ---------------------------------------------------------------------------
# 归一化器


def test_extract_usage_openai_shape():
    raw = {"usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}}
    assert _extract_token_usage(raw) == {
        "prompt_tokens": 12,
        "completion_tokens": 8,
        "total_tokens": 20,
    }


def test_extract_usage_total_fallback():
    raw = {"usage": {"prompt_tokens": 12, "completion_tokens": 8}}
    assert _extract_token_usage(raw)["total_tokens"] == 20


def test_extract_usage_unknown_returns_empty_and_no_raise():
    assert _extract_token_usage({}) == {}
    assert _extract_token_usage(None) == {}
    assert _extract_token_usage({"foo": "bar"}) == {}
    assert _extract_token_usage({"usage": "weird"}) == {}


# ---------------------------------------------------------------------------
# runner 采集 + store_raw 兼容


def test_runner_collects_turn_token_usage():
    adapter = _UsageAdapter(prompt=10, completion=5)
    traces = asyncio.run(run_cases([_case(turns=3)], adapter, concurrency=1, retry=0))
    trace = traces[0][0]
    assert len(trace.turn_token_usage) == 3
    assert all(u["total_tokens"] == 15 for u in trace.turn_token_usage)
    assert trace_total_tokens(trace) == 45


def test_token_usage_survives_store_raw_trim():
    adapter = _UsageAdapter()
    trace = asyncio.run(_run_one(_case(turns=2), adapter, timeout_s=5, retry=0))
    trimmed = trim_raw_responses(trace, "on_error")  # 成功轮次会清空 raw_responses
    assert trimmed.raw_responses == []
    # token 用量仍在（当场抽取，不依赖 raw 存活）
    assert len(trimmed.turn_token_usage) == 2
    assert trace_total_tokens(trimmed) == 30


# ---------------------------------------------------------------------------
# 判分零耦合


def test_token_does_not_affect_judging():
    case = _case()
    trace = ConversationTrace(
        messages=[ChatMessage(role="assistant", content="本回答仅供参考")],
        turn_token_usage=[{"prompt_tokens": 9, "completion_tokens": 9, "total_tokens": 18}],
    )
    r = asyncio.run(judge_all(case, trace, [HardGateJudge(), RuleJudge()]))
    assert r.gate_passed is r.hard_gate_passed
    assert all("token" not in v.name and "cost" not in v.name for v in r.verdicts)


# ---------------------------------------------------------------------------
# N-runs 折叠 + 聚合


def test_fold_collects_per_run_tokens():
    def _run(tokens: int) -> CaseResult:
        trace = ConversationTrace(
            messages=[ChatMessage(role="assistant", content="x")],
            turn_token_usage=[
                {"prompt_tokens": tokens, "completion_tokens": 0, "total_tokens": tokens}
            ],
        )
        return CaseResult(
            case=_case(), trace=trace, verdicts=[], hard_gate_passed=True, gate_passed=True
        )

    folded = fold_n_runs([[_run(100), _run(200), _run(300)]])
    assert folded[0].per_run_tokens == [100, 200, 300]


def test_token_summary_keys_and_values():
    results = [_result(True, 100), _result(True, 300), _result(True, 500)]
    report = build_report("t", results, adapter_type="stub")
    ts = report.token_summary
    assert set(ts) >= {
        "count",
        "total_prompt_tokens",
        "total_completion_tokens",
        "total_tokens",
        "avg_tokens_per_run",
    }
    assert ts["count"] == 3
    assert ts["total_tokens"] == 900
    assert ts["avg_tokens_per_run"] == 300.0
    # 未配置单价 → 不出 cost
    assert "cost" not in ts


def test_error_run_excluded_from_token_summary():
    ok = _result(True, 100)
    bad = _result(False, 9999, error="adapter exception")
    report = build_report("t", [ok, bad], adapter_type="stub")
    assert report.token_summary["count"] == 1
    assert report.token_summary["total_tokens"] == 100


def test_cost_computed_when_priced():
    # prompt=100 / completion=0 各题；单价 input=$1/M、output=$2/M
    results = [_result(True, 100), _result(True, 100)]
    snapshot = {"cost": {"currency": "USD", "input_per_million": 1.0, "output_per_million": 2.0}}
    report = build_report("t", results, adapter_type="stub", config_snapshot=snapshot)
    ts = report.token_summary
    assert ts["currency"] == "USD"
    # prompt 总 200 → 200/1e6 * 1.0 = 0.0002
    assert abs(ts["cost"] - 0.0002) < 1e-9


def test_no_token_data_renders_na():
    bad = _result(False, 0, error="boom")
    report = build_report("t", [bad], adapter_type="stub")
    assert report.token_summary == {}
    md = render_markdown(report)
    assert "成本 / Token（仅观测）" in md
    assert "无可用 token 数据" in md


# ---------------------------------------------------------------------------
# diff 降级


def test_token_diff_degrades_when_prev_missing(tmp_path: Path):
    cur = build_report("cur", [_result(True, 100)], adapter_type="stub")
    cur_path = tmp_path / "cur.json"
    prev_path = tmp_path / "prev.json"
    cur_path.write_text(cur.model_dump_json(), encoding="utf-8")
    # 上版本是历史报告，无 token_summary
    legacy = json.loads(cur.model_dump_json())
    legacy.pop("token_summary", None)
    prev_path.write_text(json.dumps(legacy), encoding="utf-8")
    out = diff_runs(cur_path, prev_path)
    assert "上版本未记录 token 数据" in out


# ---------------------------------------------------------------------------
# 历史兼容


def test_legacy_report_without_token_deserializes():
    raw = {"run_name": "legacy", "results": [], "total": 0}
    report = RunReport.model_validate(raw)
    assert report.token_summary == {}
    legacy_trace = ConversationTrace.model_validate({"messages": [], "duration_ms": 50})
    assert legacy_trace.turn_token_usage == []
