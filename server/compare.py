"""两次 run 的 DB 级对比（通过率 / 分层 / 判分指纹 / 逐样本回归）。

另含 Pairwise 对比的**可比性校验**（只卡判分尺子、放开被测 bot）与被测差异提取，
参见 OpenSpec change add-pairwise-comparison。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models_db import CaseResultRow, EvalRun


def _release_map(session: Session, run_id: int) -> dict[str, bool]:
    rows = session.execute(
        select(CaseResultRow.sample_id, CaseResultRow.release_passed).where(
            CaseResultRow.run_id == run_id
        )
    ).all()
    return {sid: bool(rp) for sid, rp in rows}


def _sample_ids(session: Session, run_id: int) -> set[str]:
    rows = session.execute(
        select(CaseResultRow.sample_id).where(CaseResultRow.run_id == run_id)
    ).scalars().all()
    return set(rows)


def _scoring_snapshot(run: EvalRun) -> Any:
    """从 config_snapshot 取判分口径（scoring 段）；缺失返回 {}。"""
    snap = run.config_snapshot or {}
    return (snap.get("scoring") if isinstance(snap, dict) else None) or {}


# 判官内部名 → 给人看的中文标签（指纹 key 取自 RunReport.judge_fingerprints）。
_JUDGE_LABELS: dict[str, str] = {
    "hard_gate": "硬门槛 HardGate",
    "rule": "规则 Rule",
    "llm": "LLM 评委",
    "scoring_point": "得分点 ScoringPoint",
    "semantic_adjudicator": "语义裁决 Adjudicator",
}


def _changed_judge_labels(fp_a: dict, fp_b: dict) -> list[str]:
    """逐判官比对指纹，返回「判分逻辑不一致」的判官中文标签列表。"""
    labels: list[str] = []
    for key in sorted(set(fp_a) | set(fp_b)):
        if fp_a.get(key) != fp_b.get(key):
            labels.append(_JUDGE_LABELS.get(key, key))
    return labels


def _scoring_diff_keys(a: dict, b: dict) -> list[str]:
    """逐字段列出评分口径（scoring）的差异 key。"""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return []
    return [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


def check_pairwise_comparable(
    session: Session, run_a: EvalRun, run_b: EvalRun
) -> list[str]:
    """可比性校验——**只卡判分尺子、放开被测 bot**。返回中文原因列表（空=可比）。

    卡：benchmark 相同、sample_id 集合一致、判分尺子一致
    （judge_fingerprints 相等且 config_snapshot.scoring 相等）、双方均已落 trace。
    放开：被测参数（system_prompt / 被测 model）差异不拦截（见 ``subject_diff``）。
    """
    reasons: list[str] = []
    if run_a.id == run_b.id:
        reasons.append("不能和自己对比，请选两个不同的评测。")
        return reasons
    if (run_a.benchmark_id or None) != (run_b.benchmark_id or None):
        reasons.append("两次评测用的题库（benchmark）不一样，题目都不同，没法对比。")
    ids_a, ids_b = _sample_ids(session, run_a.id), _sample_ids(session, run_b.id)
    if ids_a != ids_b:
        only_a = sorted(ids_a - ids_b)[:3]
        only_b = sorted(ids_b - ids_a)[:3]
        reasons.append(
            "两次评测的题目不完全相同（用例集合不一致："
            f"A 多 {len(ids_a - ids_b)} 题、B 多 {len(ids_b - ids_a)} 题"
            + (f"，如 {', '.join(only_a + only_b)}" if (only_a or only_b) else "")
            + "）。"
        )
    fp_a, fp_b = run_a.judge_fingerprints or {}, run_b.judge_fingerprints or {}
    if fp_a != fp_b:
        labels = _changed_judge_labels(fp_a, fp_b)
        who = "、".join(labels) if labels else "部分判官"
        reasons.append(
            f"判分标准不一样：两次评测里「{who}」的判分逻辑不同，"
            "等于用了两把不同的尺子量，分数没法直接比。"
        )
    else:
        scoring_diff = _scoring_diff_keys(_scoring_snapshot(run_a), _scoring_snapshot(run_b))
        if scoring_diff:
            reasons.append(
                f"算分口径不一样：两次评测在「{'、'.join(scoring_diff)}」上的算分权重/规则不同，分数没法直接比。"
            )
    if not run_a.has_traces or not run_b.has_traces:
        missing = []
        if not run_a.has_traces:
            missing.append("A")
        if not run_b.has_traces:
            missing.append("B")
        reasons.append(f"评测 {'/'.join(missing)} 没有保存对话留痕（trace），无法逐题翻出回答来对比。")
    return reasons


def pairwise_subject_diff(run_a: EvalRun, run_b: EvalRun) -> dict[str, Any]:
    """提取被测 bot 的差异（用于在总结里显式展示，不参与拦截）。"""
    diff: dict[str, Any] = {}
    ov_a = run_a.adapter_overrides or {}
    ov_b = run_b.adapter_overrides or {}
    for key in ("model", "base_url", "system_prompt"):
        va, vb = ov_a.get(key), ov_b.get(key)
        if va != vb:
            diff[key] = {"a": va, "b": vb}
    if (run_a.adapter_type or "") != (run_b.adapter_type or ""):
        diff["adapter_type"] = {"a": run_a.adapter_type, "b": run_b.adapter_type}
    return diff


def compare_runs(session: Session, current: EvalRun, against: EvalRun) -> dict[str, Any]:
    """current 相对 against 的差异。regressions = against 通过但 current 失败。"""
    cur_map = _release_map(session, current.id)
    base_map = _release_map(session, against.id)

    regressions = sorted(
        sid for sid, ok in base_map.items() if ok and not cur_map.get(sid, False)
    )
    improvements = sorted(
        sid for sid, ok in cur_map.items() if ok and not base_map.get(sid, False)
    )

    fp_cur = current.judge_fingerprints or {}
    fp_base = against.judge_fingerprints or {}
    fingerprint_changes = {
        k: {"against": fp_base.get(k), "current": fp_cur.get(k)}
        for k in set(fp_cur) | set(fp_base)
        if fp_cur.get(k) != fp_base.get(k)
    }

    return {
        "current": {
            "id": current.id,
            "run_slug": current.run_slug,
            "pass_rate": current.pass_rate,
            "passed": current.passed,
            "total": current.total,
        },
        "against": {
            "id": against.id,
            "run_slug": against.run_slug,
            "pass_rate": against.pass_rate,
            "passed": against.passed,
            "total": against.total,
        },
        "pass_rate_delta": round(current.pass_rate - against.pass_rate, 4),
        "regressions": regressions,
        "improvements": improvements,
        "judge_logic_changed": bool(fingerprint_changes),
        "fingerprint_changes": fingerprint_changes,
    }
