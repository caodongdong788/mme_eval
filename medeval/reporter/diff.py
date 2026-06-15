"""与上版本评测结果做 diff，输出 Markdown 片段。

输入是两份 JSON 报告路径，输出一段 Markdown：
  * 总体通过率变化
  * 新增的失败样本（regression）
  * 修复的失败样本（improved）
  * 各 level 通过率 delta
"""

from __future__ import annotations

import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fingerprint_warning(cur: dict, prev: dict) -> str:
    """对比两份 report 的 judge_fingerprints。

    返回值：
      - 完全一致 → ""
      - 不一致 → 带 ⚠️ 的 Markdown 表格 + 解释段
      - 上版本缺字段（旧 report） → 提示降级
    """
    cur_fps: dict[str, str] = cur.get("judge_fingerprints") or {}
    prev_fps: dict[str, str] | None = prev.get("judge_fingerprints")

    if prev_fps is None or not prev_fps:
        if not cur_fps:
            return ""  # 两边都无，不警告
        return (
            "> ℹ️ 上版本报告未记录 `judge_fingerprints`（旧报告或本提案上线前生成），"
            "无法验证判分逻辑是否一致。当前 fingerprint：`"
            + ", ".join(f"{k}={v}" for k, v in sorted(cur_fps.items()))
            + "`\n"
        )

    diffs: list[tuple[str, str, str]] = []
    for name in sorted(set(cur_fps) | set(prev_fps)):
        c = cur_fps.get(name, "(未知)")
        p = prev_fps.get(name, "(未知)")
        if c != p:
            diffs.append((name, p, c))
    if not diffs:
        return ""

    lines = [
        "> ⚠️ **判分逻辑发生变化** —— 以下 Judge 的 fingerprint 与上版本不一致，"
        "差异可能不完全来自模型 / 用例，请谨慎对比。",
        "",
        "| Judge | 上版本 | 当前 |",
        "|-|-|-|",
    ]
    for name, p, c in diffs:
        lines.append(f"| `{name}` | `{p}` | `{c}` |")
    lines.append("")
    return "\n".join(lines)


def _n_runs_warning(cur: dict, prev: dict) -> str:
    """两份 report 的 n_runs 不一致时给提示。"""
    cur_n = int(cur.get("n_runs", 1) or 1)
    prev_n = int(prev.get("n_runs", 1) or 1)
    if cur_n == prev_n:
        return ""
    return (
        f"> ℹ️ 两次评测的 N-runs 配置不同（当前 N={cur_n}，上版 N={prev_n}）。"
        "majority voting 抗噪强度不同，flaky / regression 跨版本对比意义有限。\n"
    )


def _mock_baseline_warning(cur: dict, prev: dict) -> str:
    """对比"mock 跑出来的报告"时给非可信基线警告（参见 drop-mock-adapter）。"""
    msgs: list[str] = []
    if prev.get("adapter_type") == "mock":
        msgs.append("上版本由 mock adapter 产出（已下线）")
    if cur.get("adapter_type") == "mock":
        msgs.append("当前由 mock adapter 产出")
    if not msgs:
        return ""
    return (
        "> ⚠️ 非可信基线："
        + "、".join(msgs)
        + "。mock 数据不能作为线上能力判定依据，仅做框架自检参考。\n"
    )


def _latency_diff(cur: dict, prev: dict) -> str:
    """性能（会话延迟）对比块——基于两份 report 的 ``latency_summary``。

    - 当前无延迟数据 → 返回 ""（独立「性能（仅记录）」段已显示 N/A，无需重复）。
    - 上版本缺 ``latency_summary``（历史报告）→ 返回 ℹ️ 友好提示，不抛错。
    - 两版都有 → 输出 平均 / 中位 / P90 / 最大 的 当前 / 上版 / Δ 表，
      标注延迟"仅记录、不计分、不否决"；Δ 用 ↑（变慢）/ ↓（变快）标方向。
    """
    cur_ls = cur.get("latency_summary") or {}
    if not cur_ls:
        return ""
    prev_ls = prev.get("latency_summary") or {}
    if not prev_ls:
        return (
            "> ℹ️ 上版本未记录延迟数据（历史报告），无法对比性能。"
            "本次延迟见下方「性能（仅记录）」段。\n"
        )

    rows = [("平均", "avg_ms"), ("中位", "median_ms"), ("P90", "p90_ms"), ("最大", "max_ms")]
    lines = [
        "**性能变化（会话延迟，仅记录不计分）：** 单位 ms，↑ 变慢 / ↓ 变快",
        "",
        "| 指标 | 当前 | 上版 | 变化 |",
        "|-|-|-|-|",
    ]
    for label, key in rows:
        c = float(cur_ls.get(key, 0) or 0)
        p = float(prev_ls.get(key, 0) or 0)
        d = c - p
        if d == 0:
            delta_cell = "0 (持平)"
        else:
            arrow = "↑" if d > 0 else "↓"
            pct = f"{d / p * 100:+.1f}%" if p else "—"
            delta_cell = f"{'+' if d > 0 else ''}{d:.0f} ({arrow} {pct})"
        lines.append(f"| {label} | {c:.0f} | {p:.0f} | {delta_cell} |")
    lines.append("")
    return "\n".join(lines)


def _token_diff(cur: dict, prev: dict) -> str:
    """成本 / Token 对比块——基于两份 report 的 ``token_summary``。

    - 当前无 token 数据 → 返回 ""（独立「成本 / Token（仅观测）」段已显示 N/A）。
    - 上版本缺 ``token_summary``（历史报告）→ 返回 ℹ️ 友好提示，不抛错。
    - 两版都有 → 输出 总 Token / 平均/Run /（两版都有单价时）成本 的 当前 / 上版 / Δ 表，
      标注"仅观测、不计分、不否决"；Δ 用 ↑（更多/更贵）/ ↓（更少/更省）标方向。
    """
    cur_ts = cur.get("token_summary") or {}
    if not cur_ts:
        return ""
    prev_ts = prev.get("token_summary") or {}
    if not prev_ts:
        return (
            "> ℹ️ 上版本未记录 token 数据（历史报告），无法对比成本。"
            "本次用量见下方「成本 / Token（仅观测）」段。\n"
        )

    rows = [("总 Token", "total_tokens"), ("平均/Run", "avg_tokens_per_run")]
    if "cost" in cur_ts and "cost" in prev_ts:
        rows.append(("成本", "cost"))
    lines = [
        "**成本变化（Token / 费用，仅观测不计分）：** ↑ 更多/更贵 / ↓ 更少/更省",
        "",
        "| 指标 | 当前 | 上版 | 变化 |",
        "|-|-|-|-|",
    ]
    for label, key in rows:
        c = float(cur_ts.get(key, 0) or 0)
        p = float(prev_ts.get(key, 0) or 0)
        d = c - p
        prec = 4 if key == "cost" else 0
        if d == 0:
            delta_cell = "0 (持平)"
        else:
            arrow = "↑" if d > 0 else "↓"
            pct = f"{d / p * 100:+.1f}%" if p else "—"
            delta_cell = f"{'+' if d > 0 else ''}{d:.{prec}f} ({arrow} {pct})"
        lines.append(f"| {label} | {c:.{prec}f} | {p:.{prec}f} | {delta_cell} |")
    lines.append("")
    return "\n".join(lines)


def diff_runs(current_path: Path, previous_path: Path) -> str:
    if not previous_path.exists():
        return f"_未找到上版本报告 `{previous_path}`，跳过 diff。_"
    cur = _load(current_path)
    prev = _load(previous_path)

    fp_warning = _fingerprint_warning(cur, prev)
    n_runs_warning = _n_runs_warning(cur, prev)
    mock_warning = _mock_baseline_warning(cur, prev)

    def _pass_rate(r: dict) -> float:
        return (r["passed"] / r["total"]) if r["total"] else 0.0

    cur_rate = _pass_rate(cur)
    prev_rate = _pass_rate(prev)
    delta = (cur_rate - prev_rate) * 100

    cur_results = {r["case"]["sample_id"]: r for r in cur["results"]}
    prev_results = {r["case"]["sample_id"]: r for r in prev["results"]}

    regressions: list[str] = []
    improvements: list[str] = []
    for sid, cr in cur_results.items():
        pr = prev_results.get(sid)
        if pr is None:
            continue
        if pr.get("release_passed") and not cr.get("release_passed"):
            regressions.append(sid)
        elif not pr.get("release_passed") and cr.get("release_passed"):
            improvements.append(sid)

    lines: list[str] = []
    if mock_warning:
        lines += [mock_warning, ""]
    if fp_warning:
        lines += [fp_warning, ""]
    if n_runs_warning:
        lines += [n_runs_warning, ""]
    lines += [
        f"**总通过率：** {cur_rate*100:.1f}% (上版 {prev_rate*100:.1f}%，"
        f"{'+' if delta >= 0 else ''}{delta:.1f}pp)",
        "",
    ]

    # 各 level 变化
    lines += ["**分层级通过率变化：**", ""]
    cur_by_lvl = cur.get("by_level", {})
    prev_by_lvl = prev.get("by_level", {})
    lines += ["| Level | 当前 | 上版 | Δ |", "|-|-|-|-|"]
    for lvl in sorted(set(cur_by_lvl) | set(prev_by_lvl)):
        c = cur_by_lvl.get(lvl, {"total": 0, "passed": 0})
        p = prev_by_lvl.get(lvl, {"total": 0, "passed": 0})
        cr = (c["passed"] / c["total"] * 100) if c["total"] else 0.0
        pr = (p["passed"] / p["total"] * 100) if p["total"] else 0.0
        d = cr - pr
        sign = "+" if d >= 0 else ""
        lines.append(f"| {lvl} | {cr:.1f}% | {pr:.1f}% | {sign}{d:.1f}pp |")
    lines.append("")

    lines += [f"**Regression（新增失败）：** {len(regressions)} 条"]
    for sid in regressions[:20]:
        lines.append(f"- `{sid}`")
    if not regressions:
        lines.append("- 无")
    lines.append("")

    lines += [f"**Improvement（已修复）：** {len(improvements)} 条"]
    for sid in improvements[:20]:
        lines.append(f"- `{sid}`")
    if not improvements:
        lines.append("- 无")

    latency_block = _latency_diff(cur, prev)
    if latency_block:
        lines += ["", latency_block]

    token_block = _token_diff(cur, prev)
    if token_block:
        lines += ["", token_block]

    return "\n".join(lines)
