"""Markdown 失败样本段渲染测试。

覆盖：
  * unmet_patterns 子列表（OpenSpec change `enrich-must-have-verdict-with-unmet-patterns`）
  * 失败标签 label_zh 渲染（OpenSpec change `localize-failure-tags-zh`）
"""

from __future__ import annotations

from datetime import datetime

from medeval.models import (
    CaseResult,
    ChatMessage,
    ConversationTrace,
    JudgeVerdict,
    Level,
    Pattern,
    RunReport,
    TestCase,
    Turn,
)
from medeval.reporter.markdown_report import (
    _failure_section,
    _render_verdict_line,
    _tag_to_zh_label,
    render_markdown,
)


def _make_case_result(
    verdicts: list[JudgeVerdict],
    *,
    failure_tags: list[str] | None = None,
    sample_id: str = "t",
) -> CaseResult:
    case = TestCase(
        sample_id=sample_id,
        scenario="多轮对话",
        sub_scenario="上下文记忆",
        level=Level.L2,
        turns=[Turn(role="user", content="ignored")],
    )
    trace = ConversationTrace(
        messages=[
            ChatMessage(role="user", content="问"),
            ChatMessage(role="assistant", content="答"),
        ]
    )
    return CaseResult(
        case=case,
        trace=trace,
        verdicts=verdicts,
        hard_gate_passed=True,
        release_passed=False,
        failure_tags=failure_tags if failure_tags is not None else ["inquiry_incomplete"],
        started_at=datetime(2026, 5, 28),
        finished_at=datetime(2026, 5, 28),
    )


# ---------------------------------------------------------------------------
# _render_verdict_line
# ---------------------------------------------------------------------------


def test_render_verdict_line_or_all_miss_emits_full_sublist():
    v = JudgeVerdict(
        name="rule.must_have",
        passed=False,
        reason="全部 must_have 均未命中（期望任一命中）",
        unmet_patterns=[
            Pattern(keyword="升糖"),
            Pattern(keyword="粗粮"),
            Pattern(regex=r"(白粥|油条).{0,12}(不建议|不推荐)"),
        ],
    )
    lines = _render_verdict_line(v)
    assert lines[0] == "- **rule.must_have** ✗ 全部 must_have 均未命中（期望任一命中）"
    assert lines[1] == "  - 关键词 `升糖`"
    assert lines[2] == "  - 关键词 `粗粮`"
    assert lines[3] == "  - 正则 `(白粥|油条).{0,12}(不建议|不推荐)`"
    assert len(lines) == 4


def test_render_verdict_line_and_partial_miss_emits_subset():
    v = JudgeVerdict(
        name="rule.must_have",
        passed=False,
        reason="must_have 部分未命中（要求全部命中）",
        unmet_patterns=[
            Pattern(keyword="A"),
            Pattern(keyword="C"),
        ],
    )
    lines = _render_verdict_line(v)
    assert any("`A`" in l for l in lines[1:])
    assert any("`C`" in l for l in lines[1:])
    assert all("`B`" not in l for l in lines)
    assert len(lines) == 3


def test_render_verdict_line_must_not_have_no_sublist():
    """rule.must_not_have 命中禁含 verdict 不应出现子列表。"""
    v = JudgeVerdict(
        name="rule.must_not_have",
        passed=False,
        reason="命中禁含：在家观察",
        evidence=["在家观察"],
    )
    lines = _render_verdict_line(v)
    assert lines == [
        "- **rule.must_not_have** ✗ 命中禁含：在家观察 证据：`在家观察`",
    ]


def test_render_verdict_line_hard_gate_no_sublist():
    """HardGate verdict（unmet_patterns 默认为空）不出现子列表。"""
    v = JudgeVerdict(
        name="hard_gate.disclaimer",
        passed=False,
        reason="缺少免责声明",
    )
    lines = _render_verdict_line(v)
    assert lines == ["- **hard_gate.disclaimer** ✗ 缺少免责声明"]


def test_render_verdict_line_handles_markdown_special_chars_in_regex():
    v = JudgeVerdict(
        name="rule.must_have",
        passed=False,
        reason="全部 must_have 均未命中（期望任一命中）",
        unmet_patterns=[Pattern(regex=r"\d+\s*(mg|毫克)")],
    )
    lines = _render_verdict_line(v)
    assert lines[1] == r"  - 正则 `\d+\s*(mg|毫克)`"


def test_render_verdict_line_legacy_verdict_without_field():
    """旧 JSON 加载后 unmet_patterns 默认 [] —— 退回旧单行格式。"""
    v = JudgeVerdict.model_validate(
        {
            "name": "rule.must_have",
            "passed": False,
            "reason": "全部 must_have 均未命中",
        }
    )
    lines = _render_verdict_line(v)
    assert lines == ["- **rule.must_have** ✗ 全部 must_have 均未命中"]


# ---------------------------------------------------------------------------
# _failure_section integration
# ---------------------------------------------------------------------------


def test_failure_section_includes_sublist_for_unmet_patterns():
    v = JudgeVerdict(
        name="rule.must_have",
        passed=False,
        reason="全部 must_have 均未命中（期望任一命中）",
        unmet_patterns=[
            Pattern(keyword="升糖"),
            Pattern(regex=r"(白粥|油条).{0,12}(不建议)"),
        ],
    )
    section = _failure_section([_make_case_result([v])])
    assert "- **rule.must_have** ✗ 全部 must_have 均未命中" in section
    assert "  - 关键词 `升糖`" in section
    assert "  - 正则 `(白粥|油条).{0,12}(不建议)`" in section


def test_failure_section_other_verdict_still_single_line():
    v = JudgeVerdict(
        name="rule.must_not_have",
        passed=False,
        reason="命中禁含：在家观察",
        evidence=["在家观察"],
    )
    section = _failure_section([_make_case_result([v])])
    assert "- **rule.must_not_have** ✗ 命中禁含：在家观察 证据：`在家观察`" in section
    # 子列表行不应出现
    assert "  - 关键词" not in section
    assert "  - 正则" not in section


# ---------------------------------------------------------------------------
# label_zh 渲染（OpenSpec change `localize-failure-tags-zh`）
# ---------------------------------------------------------------------------


def test_tag_to_zh_label_known_tags_translated():
    assert _tag_to_zh_label("missed_red_flag") == "漏报红旗"
    assert _tag_to_zh_label("constraint_violation") == "触发禁词"
    assert _tag_to_zh_label("improper_prescription") == "越界处方"
    assert _tag_to_zh_label("inquiry_incomplete") == "问诊不足"


def test_tag_to_zh_label_unknown_tag_falls_back_to_raw():
    """历史 / 跨版本兼容：未知 tag 降级返回原字符串，不抛 ValueError。"""
    assert _tag_to_zh_label("legacy_old_tag") == "legacy_old_tag"
    assert _tag_to_zh_label("") == ""


def test_failure_section_renders_zh_labels_in_failure_line():
    """失败样本段 `**失败标签：**` 行 MUST 渲染中文短词，不出现英文 enum value。"""
    v = JudgeVerdict(
        name="hard_gate.red_flag",
        passed=False,
        reason="未检出红旗急救表达",
    )
    r = _make_case_result(
        [v],
        failure_tags=["constraint_violation", "missed_red_flag"],
    )
    section = _failure_section([r])
    assert "**失败标签：** 触发禁词, 漏报红旗" in section
    # 不得有英文 snake_case
    assert "constraint_violation" not in section
    assert "missed_red_flag" not in section


def test_failure_section_unknown_tag_falls_back_in_label_line():
    """历史 report.json 含未知 tag 时降级为原文，混合渲染不崩。"""
    v = JudgeVerdict(name="hard_gate.red_flag", passed=False, reason="")
    r = _make_case_result(
        [v],
        failure_tags=["legacy_old_tag", "missed_red_flag"],
    )
    section = _failure_section([r])
    assert "**失败标签：** legacy_old_tag, 漏报红旗" in section


def test_failure_section_empty_failure_tags_renders_dash():
    """空 failure_tags 列表保持原行为：渲染 `—`。"""
    v = JudgeVerdict(name="rule.must_have", passed=False, reason="未命中")
    r = _make_case_result([v], failure_tags=[])
    section = _failure_section([r])
    assert "**失败标签：** —" in section


def _make_run_report(
    failure_tag_counter: dict[str, int],
    results: list[CaseResult] | None = None,
) -> RunReport:
    """构造一个最小可渲染的 RunReport。`render_markdown` 只用顶层概览字段。"""
    return RunReport(
        run_name="test_run",
        description="单测 fixture",
        adapter_type="mock",
        total=10,
        passed=7,
        hard_gate_failed=1,
        results=results or [],
        by_level={},
        by_scenario={},
        failure_tag_counter=failure_tag_counter,
        started_at=datetime(2026, 5, 28),
        finished_at=datetime(2026, 5, 28),
    )


def test_top_failure_tag_table_renders_zh_labels():
    """概览段「失败归因 Top 标签」表 MUST 渲染中文短词，无英文 / 无反引号包裹。"""
    report = _make_run_report(
        {
            "constraint_violation": 3,
            "inquiry_incomplete": 3,
            "improper_prescription": 2,
        }
    )
    md = render_markdown(report)
    assert "| 触发禁词 | 3 |" in md
    assert "| 问诊不足 | 3 |" in md
    assert "| 越界处方 | 2 |" in md
    assert "| `constraint_violation` |" not in md
    assert "| `inquiry_incomplete` |" not in md


def test_top_failure_tag_table_unknown_tag_fallback():
    """历史 tag 在 Top 标签表里降级显示原文。"""
    report = _make_run_report({"legacy_old_tag": 5, "missed_red_flag": 2})
    md = render_markdown(report)
    assert "| legacy_old_tag | 5 |" in md
    assert "| 漏报红旗 | 2 |" in md


def test_top_failure_tag_table_empty_renders_dash():
    """空 counter 时维持原行为：单元格写 `—`。"""
    report = _make_run_report({})
    md = render_markdown(report)
    assert "| — | — |" in md


