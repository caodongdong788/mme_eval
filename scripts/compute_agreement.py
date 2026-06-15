"""人审校准度量（measurement-only，**不进 CI gate**）。

定位（参见 OpenSpec change adopt-clinical-benchmark-methodology 阶段5）：
外部临床方案以人审为核心；本框架是持续自动回归引擎。两者应周期性对齐：
给定一份**人类专家打分表**（按 sample_id）与一次自动评测的 ``report.json``，
计算「自动判官 vs 人审」的一致性度量：

  * **通过一致率**：在两侧都给出通过/失败判定的用例上，判定一致的占比。
  * **Spearman 等级相关**：人审分 vs 自动综合分（``composite_score``）的秩相关，
    反映两者排序是否一致（对量纲/标定差异稳健）。

本模块**仅度量、不否决、不参与任何门槛**；纯标准库实现（无 numpy/scipy 依赖）。

人审打分表（YAML / JSON）格式（缺字段按需留空）：
    - sample_id: bc_y1_high_risk_lifestyle
      expert_score: 88          # 0–100 或 0–1，仅用于秩相关（量纲无关）
      expert_pass: true         # 可选：人审是否判定该题通过
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _ranks(values: list[float]) -> list[float]:
    """返回带并列平均秩（average ranks）的秩序列。"""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-based 平均秩
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman 秩相关系数 ρ。样本数 < 2 或某侧方差为 0 时返回 None。"""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(xs)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return None
    return cov / (vx * vy) ** 0.5


def pass_agreement(pairs: list[tuple[bool, bool]]) -> float | None:
    """通过/失败判定一致率。pairs=[(human_pass, auto_pass), ...]。空则 None。"""
    if not pairs:
        return None
    agree = sum(1 for h, a in pairs if h == a)
    return agree / len(pairs)


def _load_mapping(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("scores") or data.get("results") or []
    return list(data or [])


def compute_agreement(
    human: list[dict[str, Any]], report: dict[str, Any]
) -> dict[str, Any]:
    """对齐 human 打分与 report.json 的 results，返回度量字典。"""
    auto_by_id: dict[str, dict[str, Any]] = {}
    for r in report.get("results", []):
        sid = (r.get("case") or {}).get("sample_id")
        if sid:
            auto_by_id[sid] = r

    score_pairs: list[tuple[float, float]] = []
    pass_pairs: list[tuple[bool, bool]] = []
    matched: list[str] = []
    unmatched: list[str] = []

    for h in human:
        sid = h.get("sample_id")
        auto = auto_by_id.get(sid)
        if auto is None:
            unmatched.append(sid)
            continue
        matched.append(sid)
        es = h.get("expert_score")
        cs = auto.get("composite_score")
        if es is not None and cs is not None:
            score_pairs.append((float(es), float(cs)))
        ep = h.get("expert_pass")
        ap = auto.get("release_passed")
        if ep is not None and ap is not None:
            pass_pairs.append((bool(ep), bool(ap)))

    return {
        "matched": len(matched),
        "unmatched": unmatched,
        "pass_agreement": pass_agreement(pass_pairs),
        "pass_n": len(pass_pairs),
        "spearman": spearman(
            [p[0] for p in score_pairs], [p[1] for p in score_pairs]
        ),
        "spearman_n": len(score_pairs),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="人审 vs 自动判官一致性度量（measurement-only）")
    ap.add_argument("--report", required=True, type=Path, help="评测 report.json 路径")
    ap.add_argument("--human", required=True, type=Path, help="人审打分表 YAML/JSON 路径")
    args = ap.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    human = _load_mapping(args.human)
    m = compute_agreement(human, report)

    print("人审校准一致性度量（仅度量，不参与合格判定）")
    print(f"  对齐用例数: {m['matched']}（未匹配 {len(m['unmatched'])}）")
    pa = m["pass_agreement"]
    print(f"  通过一致率: {pa:.1%}（n={m['pass_n']}）" if pa is not None else "  通过一致率: N/A")
    sp = m["spearman"]
    print(f"  Spearman ρ: {sp:.3f}（n={m['spearman_n']}）" if sp is not None else "  Spearman ρ: N/A")
    if m["unmatched"]:
        print(f"  未匹配 sample_id: {', '.join(s for s in m['unmatched'] if s)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
