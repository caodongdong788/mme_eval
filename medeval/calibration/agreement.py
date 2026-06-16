"""人审 vs 自动判官一致性度量（measurement-only）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
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
    if not pairs:
        return None
    agree = sum(1 for h, a in pairs if h == a)
    return agree / len(pairs)


def load_human_scores(path: Path) -> list[dict[str, Any]]:
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
        "spearman": spearman([p[0] for p in score_pairs], [p[1] for p in score_pairs]),
        "spearman_n": len(score_pairs),
    }
