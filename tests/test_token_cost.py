"""medeval.reporter.token_cost characterization 单测。"""

from medeval.models import CaseResult, ChatMessage, ConversationTrace, Level, Source, TestCase, Turn
from medeval.reporter.token_cost import case_token_cost, token_cost_from_counts
from server.ingest import build_case_row


def _case_with_tokens(
    *,
    per_run_tokens: list[int] | None = None,
    turn_usage: list[dict] | None = None,
) -> CaseResult:
    kwargs: dict = {}
    if per_run_tokens is not None:
        kwargs["per_run_tokens"] = per_run_tokens
    return CaseResult(
        case=TestCase(
            sample_id="bc_token_1",
            scenario="症状",
            sub_scenario="子",
            level=Level.L3,
            source=Source.offline,
            turns=[Turn(role="user", content="test")],
        ),
        trace=ConversationTrace(
            messages=[
                ChatMessage(role="user", content="test"),
                ChatMessage(role="assistant", content="ok"),
            ],
            turn_token_usage=turn_usage or [],
        ),
        verdicts=[],
        hard_gate_passed=True,
        gate_passed=True,
        release_passed=True,
        **kwargs,
    )


def test_case_token_cost_no_usage():
    assert case_token_cost(_case_with_tokens(), None) == (None, None)


def test_case_token_cost_per_run_tokens():
    cr = _case_with_tokens(
        per_run_tokens=[100, 200],
        turn_usage=[{"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}],
    )
    total, cost = case_token_cost(cr, None)
    assert total == 300
    assert cost is None


def test_case_token_cost_with_pricing():
    cr = _case_with_tokens(
        turn_usage=[
            {"total_tokens": 1000, "prompt_tokens": 600, "completion_tokens": 400},
        ],
    )
    pricing = {
        "input_per_million": 1.0,
        "output_per_million": 2.0,
        "currency": "USD",
    }
    total, cost = case_token_cost(cr, pricing)
    assert total == 1000
    assert cost == 600 / 1_000_000 * 1.0 + 400 / 1_000_000 * 2.0


def test_token_cost_from_counts_zero_pricing():
    assert token_cost_from_counts(100, 50, {}) is None


def test_build_case_row_matches_case_token_cost():
    cr = _case_with_tokens(
        per_run_tokens=[150],
        turn_usage=[{"total_tokens": 150, "prompt_tokens": 100, "completion_tokens": 50}],
    )
    pricing = {"input_per_million": 10.0, "output_per_million": 10.0}
    expected_total, expected_cost = case_token_cost(cr, pricing)
    row = build_case_row(1, cr, pricing)
    assert row.total_tokens == expected_total
    assert row.cost == expected_cost
