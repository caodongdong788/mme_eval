"""RunReport → DB 落库器测试：落库与读回一致。"""

from __future__ import annotations

from sqlalchemy import select

from medeval.models import ChatMessage, ConversationTrace
from server.ingest import ingest_report
from server.models_db import CaseResultRow, EvalRun
from server.services.case_query import filtered_case_rows

from factories import make_case_result, make_report


def test_ingest_run_summary(session):
    report = make_report()
    ingest_report(
        session, report, judge_overrides={"model": "gpt-4o", "provider": "openai"}
    )
    session.commit()

    run = session.execute(select(EvalRun)).scalar_one()
    assert run.run_slug == "doubao_2026-06-03_1"
    assert run.status == "success"
    assert run.total == 2
    assert run.passed == 1
    assert run.pass_rate == 0.5
    assert run.adapter_type == "openai_compat"
    assert run.judge_overrides["model"] == "gpt-4o"
    assert run.by_level["L3"]["passed"] == 1
    assert run.failure_tag_counter == {}
    assert run.stability_distribution["flaky"] == 1
    assert run.grading["avg_composite"] == 33.5


def test_ingest_case_rows_scalar_columns(session):
    report = make_report()
    report.results[0].trace.turn_ttft_ms = [250.0, 350.0]
    report.ttft_summary = {"count": 1, "avg_ms": 300.0}
    ingest_report(session, report)
    session.commit()

    rows = session.execute(
        select(CaseResultRow).order_by(CaseResultRow.sample_id)
    ).scalars().all()
    assert len(rows) == 2

    bc1, bc2 = rows
    assert bc1.sample_id == "bc_001"
    assert bc1.release_passed is True
    assert bc1.stability == "stable_pass"
    assert bc1.level == "L3"
    assert bc1.latency_ms == 1200.0
    assert bc1.ttft_ms == 300.0

    run = session.execute(select(EvalRun)).scalar_one()
    assert run.ttft_summary["avg_ms"] == 300.0

    assert bc2.sample_id == "bc_002"
    assert bc2.release_passed is False
    assert bc2.medical_safety_passed is True
    assert bc2.stability == "flaky"
    assert bc2.failure_tags == []


def test_ingest_detail_json_lossless(session):
    report = make_report()
    ingest_report(session, report)
    session.commit()

    bc2 = session.execute(
        select(CaseResultRow).where(CaseResultRow.sample_id == "bc_002")
    ).scalar_one()
    detail = bc2.detail_json
    # 完整对话与 verdict 无损还原
    assert detail["case"]["sample_id"] == "bc_002"
    assert detail["trace"]["messages"][1]["content"] == "建议尽快就医"
    assert len(detail["verdicts"]) == 8
    assert detail["dimension_scores"]["medical_safety"] == 5.0
    assert detail["release_passed"] is False
    assert detail["medical_safety_passed"] is True


def test_guideline_scores_are_queryable_without_loading_detail_json(session):
    report = make_report()
    report.results[0].guideline_scores = [
        {"id": "1", "score": 3.0, "max_score": 3.0},
        {"id": "2", "score": 2.0, "max_score": 3.0},
    ]
    run = ingest_report(session, report)
    session.commit()

    rows = filtered_case_rows(session, run.id, load_detail_json=False)
    row = next(item for item in rows if item.sample_id == "bc_001")
    assert row.guideline_earned == 5.0
    assert row.guideline_max == 6.0

    partial = filtered_case_rows(
        session, run.id, guideline="partial", load_detail_json=False
    )
    assert [item.sample_id for item in partial] == ["bc_001"]


def test_ingest_report_without_tokens(session):
    """无 token 的新报告落库后 token 字段为空。"""
    report = make_report()
    ingest_report(session, report)
    session.commit()

    run = session.execute(select(EvalRun)).scalar_one()
    assert run.token_summary == {}
    rows = session.execute(select(CaseResultRow)).scalars().all()
    assert all(r.total_tokens is None and r.cost is None for r in rows)


def test_ingest_token_summary_and_case_cost(session):
    """含 token 数据 + 配置单价 → run.token_summary 与 case 级 token/cost 落库。"""
    cr = make_case_result("bc_010", release_passed=True)
    cr.trace = ConversationTrace(
        messages=[ChatMessage(role="assistant", content="x")],
        turn_token_usage=[
            {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}
        ],
    )
    cr.per_run_tokens = [1500]
    report = make_report()
    report.results = [cr]
    report.token_summary = {"count": 1, "total_tokens": 1500, "avg_tokens_per_run": 1500.0}
    report.config_snapshot = {
        "cost": {"currency": "USD", "input_per_million": 1.0, "output_per_million": 2.0}
    }
    ingest_report(session, report)
    session.commit()

    run = session.execute(select(EvalRun)).scalar_one()
    assert run.token_summary["total_tokens"] == 1500
    row = session.execute(
        select(CaseResultRow).where(CaseResultRow.sample_id == "bc_010")
    ).scalar_one()
    assert row.total_tokens == 1500
    # prompt 1000 → 1000/1e6*1 = 0.001；completion 500 → 500/1e6*2 = 0.001 → 合计 0.002
    assert abs(row.cost - 0.002) < 1e-9
