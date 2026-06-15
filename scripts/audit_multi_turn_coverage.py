"""扫描 ``cases/multi_turn/`` 下所有 YAML，输出 (depth × 失败模式) 二维分布表。

用途
----
落地 ``add-multi-turn-evaluation`` 提案 design.md 决策 2：每个深度的 10 条
case 必须按预先矩阵分布失败模式（① 上下文记忆 / ② 红旗逐步浮出 / ③ 人群晚
暴露 / ④ 边界塌方 / ⑤ 免责漂移 / ⑥ 主动追问 / ⑦ 假记忆诱导 / ⑧ 主题漂移 /
⑨ 完整问诊闭环）。本脚本把"实际分布"打出来，供作者与设计矩阵 diff。

运行
----
    python scripts/audit_multi_turn_coverage.py

输出 markdown 表格到 stdout（也可重定向到文件归档）。
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from medeval.loader import load_cases  # noqa: E402

# 失败模式 tag → 矩阵行标签（与 design.md 决策 2 矩阵一一对应）
TAG_TO_MODE = {
    "context_recall": "① 上下文记忆",
    "escalation": "② 红旗逐步浮出",
    "population_late": "③ 人群晚暴露",
    "boundary": "④ 边界塌方",
    "disclaimer_drift": "⑤ 免责漂移",
    "active_inquiry": "⑥ 主动追问",
    "fake_memory": "⑦ 假记忆诱导",
    "topic_drift": "⑧ 主题漂移",
    "full_loop": "⑨ 完整问诊闭环",
}

EXPECTED_MATRIX = {
    "① 上下文记忆":     {2: 2, 3: 1, 4: 1, 5: 1},
    "② 红旗逐步浮出":   {2: 2, 3: 2, 4: 1, 5: 1},
    "③ 人群晚暴露":     {2: 1, 3: 1, 4: 1, 5: 1},
    "④ 边界塌方":       {2: 1, 3: 1, 4: 2, 5: 2},
    "⑤ 免责漂移":       {2: 1, 3: 2, 4: 1, 5: 1},
    "⑥ 主动追问":       {2: 1, 3: 1, 4: 0, 5: 0},
    "⑦ 假记忆诱导":     {2: 2, 3: 1, 4: 1, 5: 1},
    "⑧ 主题漂移":       {2: 0, 3: 0, 4: 0, 5: 1},
    "⑨ 完整问诊闭环":   {2: 0, 3: 1, 4: 3, 5: 2},
}


def classify(tags: list[str]) -> str | None:
    """同一条 case 可能被打多个模式 tag，按上面字典优先序取第一个命中的。

    没有任何 tag 命中时返回 None（说明 case 作者忘了打 tag）。
    """
    for tag, mode in TAG_TO_MODE.items():
        if tag in tags:
            return mode
    return None


def main() -> int:
    cases = load_cases(include=["cases/multi_turn"], base_dir=ROOT)
    by_mode_depth: dict[tuple[str, int], list[str]] = defaultdict(list)
    untagged: list[str] = []

    for case in cases:
        depth = len([t for t in case.turns if t.role == "user"])
        mode = classify(case.tags)
        if mode is None:
            untagged.append(case.sample_id)
            continue
        by_mode_depth[(mode, depth)].append(case.sample_id)

    depths = [2, 3, 4, 5]
    modes = list(TAG_TO_MODE.values())

    print(f"# 多轮用例覆盖审计  ({len(cases)} 条)\n")
    print("## 实际分布")
    header = "| 失败模式 | " + " | ".join(f"d{d}" for d in depths) + " | 行总 |"
    sep = "|" + "|".join(["---"] * (len(depths) + 2)) + "|"
    print(header)
    print(sep)
    col_totals = {d: 0 for d in depths}
    grand = 0
    for mode in modes:
        cells = []
        row_total = 0
        for d in depths:
            n = len(by_mode_depth.get((mode, d), []))
            cells.append(str(n))
            col_totals[d] += n
            row_total += n
        print(f"| {mode} | " + " | ".join(cells) + f" | {row_total} |")
        grand += row_total
    print(
        "| **列总** | "
        + " | ".join(f"**{col_totals[d]}**" for d in depths)
        + f" | **{grand}** |\n"
    )

    print("## 与 design.md 决策 2 矩阵对照")
    diff_count = 0
    for mode in modes:
        for d in depths:
            actual = len(by_mode_depth.get((mode, d), []))
            expected = EXPECTED_MATRIX.get(mode, {}).get(d, 0)
            if actual != expected:
                print(
                    f"- ⚠ {mode} × d{d}: 期望 {expected} 实际 {actual} "
                    f"(用例: {by_mode_depth.get((mode, d), [])})"
                )
                diff_count += 1
    if diff_count == 0:
        print("- ✓ 与设计矩阵完全一致\n")
    else:
        print(f"\n共 {diff_count} 处偏差。\n")

    if untagged:
        print("## 未识别失败模式 tag 的用例")
        for sid in untagged:
            print(f"- {sid}")
        return 1

    return 0 if diff_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
