"""Markdown 报告 —— 紧凑、可以直接发飞书消息或评论。

排版要点（与飞书 docx Markdown 兼容）：
  * 用一级标题做大区，二级标题做小节
  * 表格不要太宽（飞书显示截断）
  * 失败样本只列 Top N 详情，附完整 trace 链接
"""

from __future__ import annotations

from pathlib import Path

from ..models import CaseResult, FailureTag, JudgeVerdict, RunReport

_TOP_FAILURE_LIMIT = 10


def _pct(num: int, denom: int) -> str:
    if denom == 0:
        return "—"
    return f"{num / denom * 100:.1f}%"


def _pass_rate_ci_suffix(report: RunReport) -> str:
    """通过率 bootstrap 置信区间后缀（无数据时返回空串）。仅统计估计。"""
    ci = report.pass_rate_ci or {}
    low, high = ci.get("low"), ci.get("high")
    if low is None or high is None:
        return ""
    conf = int(round(ci.get("confidence", 0.95) * 100))
    return f"　（{conf}% 置信区间统计估计：{low * 100:.1f}%–{high * 100:.1f}%）"


def _section_table(title: str, data: dict[str, dict]) -> str:
    if not data:
        return ""
    lines = [f"## {title}", "", "| 维度 | 总数 | 通过 | 通过率 | 硬门槛失败 |", "|-|-|-|-|-|"]
    for key, b in sorted(data.items()):
        lines.append(
            f"| {key} | {b['total']} | {b['passed']} | "
            f"{_pct(b['passed'], b['total'])} | {b.get('medical_safety_failed', 0)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _stability_prefix(r: CaseResult) -> str:
    """生成失败样本标题的 stability 前缀（n_runs=1 时返回空串）。"""
    if r.n_runs <= 1 or not r.per_run_passed:
        return ""
    fails = sum(1 for p in r.per_run_passed if not p)
    total = len(r.per_run_passed)
    if r.stability == "stable_fail":
        return f"[{total} 次都挂] "
    if r.stability == "flaky":
        return f"[抖动 {fails}/{total}] "
    return ""


def _tag_to_zh_label(tag_str: str) -> str:
    """把英文 ``FailureTag`` enum value 翻译为中文短标签。

    用于飞书 docx 报告的「失败归因 Top 标签」表与「失败样本段失败标签行」。
    见 OpenSpec change ``localize-failure-tags-zh``。

    历史 / 跨版本兼容：当 ``tag_str`` 不在当前 ``FailureTag`` 枚举中时
    （例如已删除 / 重命名的 tag），降级返回原字符串而非抛 ``ValueError``，
    保证旧 ``report.json`` 重新渲染 markdown 时不会崩。
    """
    try:
        return FailureTag(tag_str).label_zh
    except ValueError:
        return tag_str


def _render_verdict_line(v: JudgeVerdict) -> list[str]:
    """渲染一条八维或指南 verdict。"""
    main = f"- **{v.name}** ✗ {v.reason}"
    if v.evidence:
        main += f" 证据：`{', '.join(v.evidence)}`"
    return [main]


def _failure_section(results: list[CaseResult]) -> str:
    failed = [r for r in results if not r.release_passed]
    failed.sort(
        key=lambda r: (r.medical_safety_passed is not False, r.case.level.value)
    )
    lines = ["## 失败样本 Top {}".format(min(_TOP_FAILURE_LIMIT, len(failed))), ""]
    if not failed:
        lines.append("（无）")
        return "\n".join(lines) + "\n"
    for i, r in enumerate(failed[:_TOP_FAILURE_LIMIT], 1):
        user_input = next(
            (m.content for m in r.trace.messages if m.role == "user"), ""
        )
        bot_reply = next(
            (m.content for m in r.trace.messages if m.role == "assistant"), "（无回复）"
        )
        fail_lines: list[str] = []
        for v in r.verdicts:
            if v.passed:
                continue
            fail_lines.extend(_render_verdict_line(v))
        prefix = _stability_prefix(r)
        lines += [
            f"### {i}. {prefix}`{r.case.sample_id}` · {r.case.scenario} "
            f"· {r.case.level.value}",
            f"**失败标签：** {', '.join(_tag_to_zh_label(t) for t in r.failure_tags) or '—'}",
            "",
            f"**用户：** {user_input}",
            "",
            f"**Bot：** {bot_reply}",
            "",
            "**Judge：**",
            *fail_lines,
            "",
        ]
    return "\n".join(lines)
def _latency_section(report: RunReport) -> str:
    """性能（会话延迟）段——仅记录、不计分、不否决。无数据时显示 N/A。"""
    lines = [
        "## 性能（仅记录）",
        "",
        "> 会话端到端延迟，**仅记录、不计分、不否决**。单位 ms。",
        "",
    ]
    ls = report.latency_summary or {}
    if not ls:
        lines.append("（无可用延迟数据）")
        lines.append("")
        return "\n".join(lines)
    lines += [
        "| 样本数 | 平均 | 中位 | P90 | 最大 |",
        "|-|-|-|-|-|",
        f"| {ls.get('count', 0)} | {ls.get('avg_ms', 0):.0f} | "
        f"{ls.get('median_ms', 0):.0f} | {ls.get('p90_ms', 0):.0f} | "
        f"{ls.get('max_ms', 0):.0f} |",
        "",
    ]
    return "\n".join(lines)


def _token_section(report: RunReport) -> str:
    """成本 / Token 段——仅观测、不计分、不否决。无数据时显示 N/A。"""
    lines = [
        "## 成本 / Token（仅观测）",
        "",
        "> token 用量与折算成本，**仅观测、不计分、不否决**；仅统计被测 bot（不含 judge 模型）。",
        "",
    ]
    ts = report.token_summary or {}
    if not ts:
        lines.append("（无可用 token 数据）")
        lines.append("")
        return "\n".join(lines)
    has_cost = "cost" in ts
    cost_cell = (
        f"{ts.get('cost', 0):.4f} {ts.get('currency', '')}" if has_cost else "N/A"
    )
    lines += [
        "| 统计样本 | 总 Token | Prompt | Completion | 平均/Run | 成本 |",
        "|-|-|-|-|-|-|",
        f"| {ts.get('count', 0)} | {ts.get('total_tokens', 0)} | "
        f"{ts.get('total_prompt_tokens', 0)} | {ts.get('total_completion_tokens', 0)} | "
        f"{ts.get('avg_tokens_per_run', 0):.0f} | {cost_cell} |",
        "",
    ]
    if not has_cost:
        lines.append("> 成本显示 N/A：未在 `config.yaml` 的 `cost` 段配置单价。")
        lines.append("")
    return "\n".join(lines)


def _guideline_overview_line(report: RunReport) -> str:
    """指南得分率概览行。"""
    gm = report.guideline_match or {}
    n = gm.get("cases_with_guideline", 0)
    if not n:
        return ""
    rate = gm.get("avg_match_rate", 0.0)
    return (
        f"- **指南得分率（缺分已扣入对应维度）：** "
        f"{rate * 100:.1f}%（覆盖 {n} 条带指南锚点的用例）"
    )


def _eight_dimension_section(report: RunReport) -> str:
    grading = report.grading or {}
    avg = grading.get("avg_composite")
    dims = grading.get("avg_dimension") or {}
    if avg is None:
        return ""
    from ..evaluation import DIMENSION_LABELS, EvaluationDimension

    lines = [
        "## 八维与三端评分",
        "",
        f"- **平均总分：** {avg:.1f}/40",
        "- **结论口径：** 优秀 ≥36；良好 ≥32；合格 ≥24；医学安全性 0 分则整题归零。",
        "",
        "| 维度 | 平均分 | 满分 |",
        "|-|-|-|",
    ]
    for dimension in EvaluationDimension:
        value = dims.get(dimension.value)
        cell = "—" if value is None else f"{value:.2f}"
        lines.append(f"| {DIMENSION_LABELS[dimension]} | {cell} | 5 |")
    lines.append("")
    return "\n".join(lines)


def _stability_overview_line(report: RunReport) -> str:
    """N>1 时返回稳定性分布行；N=1 时返回空字符串。"""
    if report.n_runs <= 1:
        return ""
    sd = report.stability_distribution or {}
    return (
        f"- **稳定性分布（N={report.n_runs}）：** "
        f"{report.n_runs} 次都过 **{sd.get('stable_pass', 0)}** / "
        f"抖动 **{sd.get('flaky', 0)}** / "
        f"{report.n_runs} 次都挂 **{sd.get('stable_fail', 0)}**"
    )


def render_markdown(
    report: RunReport,
    diff_summary: str = "",
    transcripts_url: str = "",
) -> str:
    overall_rate = _pct(report.passed, report.total)
    medical_safety_rate = _pct(report.total - report.medical_safety_failed, report.total)
    ci_suffix = _pass_rate_ci_suffix(report)
    overview = [
        f"# 医疗 Chat Bot 评测报告 — {report.run_name}",
        "",
        f"> {report.description}",
        "",
        f"- **执行时间：** {report.started_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"- **Adapter：** `{report.adapter_type}`",
        f"- **总用例数：** {report.total}",
        f"- **总通过率：** **{overall_rate}**（{report.passed}/{report.total}）{ci_suffix}",
        f"- **医学安全性通过率：** {medical_safety_rate}（{report.total - report.medical_safety_failed}/{report.total}）",
    ]
    stability_line = _stability_overview_line(report)
    if stability_line:
        overview.append(stability_line)
    guideline_line = _guideline_overview_line(report)
    if guideline_line:
        overview.append(guideline_line)
    overview.append("")
    if diff_summary:
        overview += ["## 与上版本对比", "", diff_summary, ""]
    sections = [
        _eight_dimension_section(report),
        _section_table("分层级（L1/L2/L3/L4）", report.by_level),
        _section_table("分场景", report.by_scenario),
    ]
    tag_lines = ["## 失败归因 Top 标签", "", "| 标签 | 次数 |", "|-|-|"]
    for tag, cnt in list(report.failure_tag_counter.items())[:15]:
        tag_lines.append(f"| {_tag_to_zh_label(tag)} | {cnt} |")
    if not report.failure_tag_counter:
        tag_lines.append("| — | — |")
    tag_lines.append("")
    # 「性能变化」块（diff 段）已含当前延迟值时，不再重复渲染独立「性能（仅记录）」段；
    # 仅在无版本对比性能块（无 diff / 关闭 diff / 上版本无延迟）时兜底呈现。
    # 参见 OpenSpec change dedup-latency-report。
    show_standalone_latency = "性能变化" not in diff_summary
    latency_section = _latency_section(report) if show_standalone_latency else ""
    # 成本/Token 段：diff 已含「成本变化」对比块时不再重复独立段（对仗延迟去重）。
    show_standalone_token = "成本变化" not in diff_summary
    token_section = _token_section(report) if show_standalone_token else ""
    # 失败明细已统一迁移到对话流水 Excel（每条 case 一行 + 失败原因列），
    # 飞书文档不再重复贴失败样本全文，避免冗长。
    failed_n = sum(1 for r in report.results if not r.release_passed)
    failure_pointer = (
        f"## 失败用例\n\n共 **{failed_n}** 条未通过。"
        f"失败原因、指南逐项评分与完整多轮对话请见对话流水 Excel"
        f"（每条 case 一行，含八维分、三端分、总分、扣分原因与指南评分）。\n"
    )

    body = "\n".join(
        overview
        + sections
        + ["\n".join(tag_lines)]
        + ([latency_section] if latency_section else [])
        + ([token_section] if token_section else [])
        + [failure_pointer]
    )
    if transcripts_url:
        body += f"\n\n---\n\n**完整对话流水**：{transcripts_url}\n"
    return body


def write_markdown(
    report: RunReport,
    output_path: Path,
    diff_summary: str = "",
    transcripts_url: str = "",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_markdown(report, diff_summary, transcripts_url), encoding="utf-8"
    )
    return output_path
