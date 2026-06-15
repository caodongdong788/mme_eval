"""用例明细对话轮数：cases 返回 n_turns；turns=single/multi 过滤。"""

from __future__ import annotations

from factories import make_case_result, make_report

from medeval.models import (
    ChatMessage,
    ConversationTrace,
    JudgeVerdict,
    Level,
    ScoreProfile,
    Source,
    TestCase,
    Turn,
)
from server.benchmarks import ensure_builtin_benchmark
from server.db import session_scope
from server.ingest import ingest_report


def _multi_turn_result(sample_id: str):
    """两轮用户提问的用例（n_turns 应为 2）。"""
    case = TestCase(
        sample_id=sample_id,
        scenario="多轮",
        sub_scenario="上下文",
        level=Level.L3,
        source=Source.offline,
        score_profile=ScoreProfile.red_flag,
        turns=[
            Turn(role="user", content="第一问"),
            Turn(role="user", content="第二问"),
        ],
    )
    base = make_case_result(sample_id)
    base.case = case
    base.trace = ConversationTrace(
        messages=[
            ChatMessage(role="user", content="第一问"),
            ChatMessage(role="assistant", content="答一"),
            ChatMessage(role="user", content="第二问"),
            ChatMessage(role="assistant", content="答二"),
        ],
        duration_ms=1500,
    )
    base.verdicts = [JudgeVerdict(name="hard_gate.red_flag", passed=True)]
    return base


def _seed(settings) -> int:
    with session_scope() as s:
        bm = ensure_builtin_benchmark(s, settings)
        s.flush()
        report = make_report("turns_run")  # bc_001 / bc_002 均单轮
        report.results.append(_multi_turn_result("bc_multi"))
        report.total = len(report.results)
        run = ingest_report(s, report, benchmark_id=bm.id)
        s.flush()
        return run.id


def test_cases_include_n_turns(client, settings):
    rid = _seed(settings)
    rows = client.get(f"/api/runs/{rid}/cases").json()
    by = {r["sample_id"]: r for r in rows}
    assert by["bc_001"]["n_turns"] == 1
    assert by["bc_multi"]["n_turns"] == 2


def test_filter_turns_multi(client, settings):
    rid = _seed(settings)
    multi = client.get(f"/api/runs/{rid}/cases", params={"turns": "multi"}).json()
    assert {r["sample_id"] for r in multi} == {"bc_multi"}


def test_filter_turns_single(client, settings):
    rid = _seed(settings)
    single = client.get(f"/api/runs/{rid}/cases", params={"turns": "single"}).json()
    ids = {r["sample_id"] for r in single}
    assert "bc_multi" not in ids
    assert "bc_001" in ids
