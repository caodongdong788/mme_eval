"""trace 落盘模块单测（change 2026-06-04-persist-traces-rejudge）。

覆盖：
  - round-trip：write_traces → read_traces 逐字段一致
  - store_raw 三档裁剪：never / on_error / always
  - PartialTraceWriter + finalize_traces：增量写 → 压缩落定
  - adapter_fingerprint：排除 api_key、同 bot 同指纹
  - per_case_traces：按用例顺序与 n_runs 重建二维结构
"""

from __future__ import annotations

from pathlib import Path

from medeval import trace_store
from medeval.models import ChatMessage, ConversationTrace, Level, TestCase, Turn


def _trace(reply: str = "ok", error: str | None = None, raw=None) -> ConversationTrace:
    return ConversationTrace(
        messages=[
            ChatMessage(role="user", content="q"),
            ChatMessage(role="assistant", content=reply),
        ],
        raw_responses=raw if raw is not None else [{"big": "payload" * 50}],
        duration_ms=123,
        turn_latencies_ms=[12.5],
        error=error,
    )


def _case(sid: str) -> TestCase:
    return TestCase(sample_id=sid, scenario="s", level=Level.L2, turns=[Turn(content="q")])


def _meta(fp: str = "fp123", store_raw: str = "always", n_runs: int = 1, n_cases: int = 1):
    return {
        "schema": trace_store.SCHEMA_VERSION,
        "adapter_fingerprint": fp,
        "store_raw": store_raw,
        "n_runs": n_runs,
        "n_cases": n_cases,
    }


# --- round-trip ------------------------------------------------------------


def test_write_read_roundtrip(tmp_path: Path):
    cases = [_case("a"), _case("b")]
    per_case = [[_trace("ra")], [_trace("rb")]]
    trace_store.write_traces(tmp_path, cases, per_case, store_raw="always", meta=_meta(n_cases=2))

    bundle = trace_store.read_traces(tmp_path)
    assert bundle is not None
    assert bundle.meta["adapter_fingerprint"] == "fp123"
    t = bundle.by_key[("a", 0)]
    assert t.messages[-1].content == "ra"
    assert t.duration_ms == 123
    assert t.turn_latencies_ms == [12.5]
    assert bundle.by_key[("b", 0)].messages[-1].content == "rb"


def test_per_case_traces_rebuild_order(tmp_path: Path):
    cases = [_case("a"), _case("b")]
    per_case = [[_trace("a0"), _trace("a1")], [_trace("b0"), _trace("b1")]]
    trace_store.write_traces(tmp_path, cases, per_case, store_raw="always", meta=_meta(n_runs=2, n_cases=2))
    bundle = trace_store.read_traces(tmp_path)
    rebuilt = bundle.per_case_traces(cases, 2)
    assert [t.messages[-1].content for t in rebuilt[0]] == ["a0", "a1"]
    assert [t.messages[-1].content for t in rebuilt[1]] == ["b0", "b1"]


# --- store_raw 裁剪 --------------------------------------------------------


def test_store_raw_never_drops_all():
    t = _trace(error=None)
    out = trace_store.trim_raw_responses(t, "never")
    assert out.raw_responses == []
    # 文本/延迟/error 不动
    assert out.messages == t.messages
    assert out.turn_latencies_ms == t.turn_latencies_ms


def test_store_raw_on_error_keeps_only_errors():
    ok = trace_store.trim_raw_responses(_trace(error=None), "on_error")
    bad = trace_store.trim_raw_responses(_trace(error="boom"), "on_error")
    assert ok.raw_responses == []
    assert bad.raw_responses  # 报错留全量


def test_store_raw_always_keeps():
    t = _trace(error=None)
    out = trace_store.trim_raw_responses(t, "always")
    assert out.raw_responses == t.raw_responses


def test_write_applies_store_raw(tmp_path: Path):
    cases = [_case("a")]
    per_case = [[_trace(error=None)]]
    trace_store.write_traces(tmp_path, cases, per_case, store_raw="never", meta=_meta(store_raw="never"))
    bundle = trace_store.read_traces(tmp_path)
    assert bundle.by_key[("a", 0)].raw_responses == []


# --- 增量写 + finalize -----------------------------------------------------


def test_partial_writer_then_finalize(tmp_path: Path):
    w = trace_store.PartialTraceWriter(tmp_path, store_raw="always", meta=_meta(n_runs=2, n_cases=1))
    w.record("a", 0, 0, _trace("r0"))
    w.record("a", 0, 1, _trace("r1"))
    w.close()
    # finalize 前 partial 存在
    assert (tmp_path / trace_store.PARTIAL).exists()
    gz = trace_store.finalize_traces(tmp_path)
    assert gz is not None and gz.exists()
    assert not (tmp_path / trace_store.PARTIAL).exists()
    bundle = trace_store.read_traces(tmp_path)
    assert ("a", 0) in bundle.by_key and ("a", 1) in bundle.by_key


def test_read_falls_back_to_partial(tmp_path: Path):
    # 只有 partial（崩溃未 finalize）也能读
    w = trace_store.PartialTraceWriter(tmp_path, store_raw="always", meta=_meta())
    w.record("a", 0, 0, _trace("r0"))
    w.close()
    bundle = trace_store.read_traces(tmp_path)
    assert bundle is not None
    assert bundle.by_key[("a", 0)].messages[-1].content == "r0"


def test_read_missing_returns_none(tmp_path: Path):
    assert trace_store.read_traces(tmp_path) is None


# --- adapter 指纹 ----------------------------------------------------------


def test_adapter_fingerprint_excludes_api_key():
    cfg1 = {"type": "openai_compat", "openai_compat": {"model": "m", "system_prompt": "p", "api_key": "secret1"}}
    cfg2 = {"type": "openai_compat", "openai_compat": {"model": "m", "system_prompt": "p", "api_key": "secret2"}}
    fp1 = trace_store.adapter_fingerprint("openai_compat", cfg1)
    fp2 = trace_store.adapter_fingerprint("openai_compat", cfg2)
    assert fp1 == fp2  # api_key 不同不影响指纹


def test_adapter_fingerprint_differs_on_system_prompt():
    cfg1 = {"openai_compat": {"model": "m", "system_prompt": "p1"}}
    cfg2 = {"openai_compat": {"model": "m", "system_prompt": "p2"}}
    assert trace_store.adapter_fingerprint("openai_compat", cfg1) != trace_store.adapter_fingerprint(
        "openai_compat", cfg2
    )
