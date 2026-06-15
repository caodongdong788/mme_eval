"""transcript_cells 纯内容派生单测（change 2026-06-02-split-transcript-cells）。

这些 helper 现在与 openpyxl 解耦，可不构造 workbook 直接断言。
"""

from __future__ import annotations

from medeval.models import (
    CaseResult,
    ChatMessage,
    ConversationTrace,
    JudgeVerdict,
    Level,
    TestCase,
)
from medeval.reporter.transcript_cells import (
    _display_lines,
    _fmt_dim_ratio,
    _fmt_points,
    _highlight_runs,
    _mark_plain,
    _scoring_point_cells,
    _test_content_cell,
    _truncate,
    _turn_cell,
    _turns,
    _user_turn_count,
    _MAX_CELL_LEN,
)


def _case(**kw) -> TestCase:
    base = dict(sample_id="bc_x", scenario="场景", level=Level.L2,
                turns=[])
    base.update(kw)
    return TestCase(**base)  # type: ignore[arg-type]


def _result(msgs, *, verdicts=None, **kw) -> CaseResult:
    return CaseResult(
        case=_case(),
        trace=ConversationTrace(messages=msgs, **{k: v for k, v in kw.items() if k == "turn_latencies_ms"}),
        verdicts=verdicts or [],
        hard_gate_passed=True,
        gate_passed=True,
        release_passed=True,
    )


# --- 文本工具 --------------------------------------------------------------


def test_fmt_points_and_ratio():
    assert _fmt_points(None) == "N/A"
    assert _fmt_points(0.3) == "0.30"
    assert _fmt_points(-0.1) == "-0.10"
    assert _fmt_dim_ratio(None, 0.3) == "N/A"
    assert _fmt_dim_ratio(0.3, 0.3) == "0.30/0.30"


def test_truncate_respects_cell_limit():
    short = "abc"
    assert _truncate(short) == short
    long = "x" * (_MAX_CELL_LEN + 10)
    out = _truncate(long)
    assert len(out) == _MAX_CELL_LEN
    assert out.endswith("trace）")


def test_display_lines_cjk_double_width():
    # 10 个中文 = 20 单位宽，列宽 10 → 2 行
    assert _display_lines("中" * 10, 10) == 2
    # 空行也算 1 行
    assert _display_lines("a\n\nb", 70) == 3


# --- 关键词标记 ------------------------------------------------------------


def test_highlight_runs_merges_overlaps_case_insensitive():
    runs = _highlight_runs("Hello hello", ["hello"])
    assert [seg for seg, hit in runs if hit] == ["Hello", "hello"]


def test_highlight_runs_no_match():
    assert _highlight_runs("abc", ["zzz"]) == [("abc", False)]


def test_mark_plain_wraps_hits():
    assert _mark_plain("看急诊", ["急诊"]) == "看【急诊】"
    assert _mark_plain("无命中", ["xx"]) == "无命中"


def test_turn_cell_marks_bot_keywords():
    cell = _turn_cell("我头痛", "请立即就医", ["就医"])
    assert "👤 用户：我头痛" in cell
    assert "【就医】" in cell


def test_turn_cell_no_reply():
    cell = _turn_cell("问题", None, ["x"])
    assert "（无回复）" in cell


# --- turns 折叠 ------------------------------------------------------------


def test_turns_folds_pairs_and_skips_system():
    msgs = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="u1"),
        ChatMessage(role="assistant", content="a1"),
        ChatMessage(role="user", content="u2"),  # 末轮无回复
    ]
    r = _result(msgs, turn_latencies_ms=[123.0])
    pairs = _turns(r)
    assert pairs == [("u1", "a1", 123.0), ("u2", None, None)]
    assert _user_turn_count(r) == 2


# --- 测试内容列 ------------------------------------------------------------


def test_test_content_cell_uses_passed_profile_name():
    r = _result([])
    out = _test_content_cell(r, "red_flag")
    assert "red_flag（红旗 / 分诊）" in out  # 中文标签来自 _PROFILE_ZH


def test_test_content_cell_unknown_profile_falls_back_to_name():
    r = _result([])
    out = _test_content_cell(r, "weird")
    assert "weird（weird）" in out


# --- 得分点列 --------------------------------------------------------------


def test_scoring_point_cells_dash_when_absent():
    assert _scoring_point_cells(_result([])) == ("—", "—", "—")


def test_scoring_point_cells_render_summary_and_points():
    verdicts = [
        JudgeVerdict(name="scoring_point.summary", passed=True, score=3, max_score=4,
                     reason="净分"),
        JudgeVerdict(name="scoring_point.point1", passed=True, score=1, max_score=1,
                     reason="命中要点", evidence=["建议就医"]),
        JudgeVerdict(name="scoring_point.point2", passed=False, score=0, max_score=0,
                     reason="触发惩罚"),
    ]
    net, gm, detail = _scoring_point_cells(_result([], verdicts=verdicts))
    assert net == "3/4"
    assert "✓ 建议就医 — 命中要点" in detail
    assert "✗ 触发惩罚（负分/惩罚） — 触发惩罚" in detail
