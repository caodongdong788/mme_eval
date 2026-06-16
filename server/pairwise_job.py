"""Pairwise 对比的后台执行 + 孤儿回收 + 汇总（OpenSpec change add-pairwise-comparison）。

零改判分内核：复用 ``medeval.pairwise.PairwiseComparator`` + 两个 run 已落库的
``CaseResultRow.detail_json``（含 trace/case）。产出**相对偏好**，不写任何 gate。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select

from .constants import PAIRWISE_JOB_USER_ERROR

from .db import session_scope
from .models_db import (
    CaseResultRow,
    JudgeModelConfig,
    PairwiseCaseVerdict,
    PairwiseComparison,
)

log = logging.getLogger(__name__)

_DIMENSIONS = ("safety", "function", "experience")
CONFIDENCE_KINDS = frozenset({"high", "order", "safety", "human"})


def _machine_confidence_kind(v: PairwiseCaseVerdict) -> str:
    """机器判定的 confidence_kind（非人工）。"""
    if v.confidence == "high":
        return "high"
    return "safety" if v.swap_consistent else "order"


def verdict_effective_row(v: PairwiseCaseVerdict) -> dict[str, Any]:
    """逐用例有效值（汇总/展示单一信任源）。"""
    if v.human_calibrated:
        return {
            "sample_id": v.sample_id,
            "winner": v.human_winner or v.winner,
            "dimension_winners": dict(v.human_dimension_winners or {}),
            "reason": (v.human_reason or "").strip(),
            "confidence_kind": "human",
            "human_calibrated": True,
        }
    return {
        "sample_id": v.sample_id,
        "winner": v.winner,
        "dimension_winners": dict(v.dimension_winners or {}),
        "reason": (v.reason or "").strip(),
        "confidence_kind": _machine_confidence_kind(v),
        "human_calibrated": False,
    }


def reconcile_orphaned_pairwise() -> int:
    """启动时把残留 running 的 pairwise 比较置 failed（进程内任务态丢失）。幂等。"""
    count = 0
    with session_scope() as session:
        rows = session.execute(
            select(PairwiseComparison).where(PairwiseComparison.status == "running")
        ).scalars().all()
        for row in rows:
            row.status = "failed"
            row.error_msg = "服务重启导致对比中断（孤儿任务回收）"
            if row.finished_at is None:
                row.finished_at = datetime.utcnow()
            count += 1
    return count


def _build_comparator(judge_model_id: int):
    """从判分模型库解析连接配置，构造 PairwiseComparator。

    返回 (comparator, 模型显示名, 题间并发度)。并发度仅作用于对比，缺省/非法回落为 4。
    """
    from medeval.pairwise import PairwiseComparator

    with session_scope() as session:
        jm = session.get(JudgeModelConfig, judge_model_id)
        if jm is None:
            raise ValueError(f"判分模型 {judge_model_id} 不存在")
        cfg = dict(
            provider=jm.provider or "openai",
            model=jm.model,
            base_url=jm.base_url or "",
            api_version=jm.api_version or "",
            api_key=jm.api_key or "",
            temperature=jm.temperature if jm.temperature is not None else 0.0,
        )
        label = jm.model or jm.name
        concurrency = max(1, int(jm.pairwise_concurrency or 4))
    return PairwiseComparator(**cfg), label, concurrency


def _detail_map(session, run_id: int) -> dict[str, dict[str, Any]]:
    """run 内每个 sample_id 的 detail_json（含 trace/case）。"""
    rows = session.execute(
        select(CaseResultRow.sample_id, CaseResultRow.detail_json, CaseResultRow.release_passed)
        .where(CaseResultRow.run_id == run_id)
    ).all()
    return {sid: {"detail": dj or {}, "release_passed": bool(rp)} for sid, dj, rp in rows}


def _derive_confidence(
    winner: str, swap_consistent: bool, dimension_winners: dict[str, Any] | None
) -> str:
    """按「换序稳健」口径从已存字段重导 confidence（历史回填用，不重调 LLM）。

    - winner 决定性（A/B）→ high
    - tie 且顺序敏感（换序不一致）→ low
    - tie 且换序一致 → 真平局（三维全 tie）= high；留有决定性维度（被安全降级）= low

    最后一档是启发式：旧库里「真平局」与「安全降级」都长成 (tie, swap_consistent=true)，
    用 dimension_winners 是否有决定性维度来区分（安全降级必有一维向 pre-winner 倾斜）。
    """
    if winner in ("A", "B"):
        return "high"
    if not swap_consistent:
        return "low"
    dims = dimension_winners or {}
    any_decisive = any(dims.get(d) in ("A", "B") for d in _DIMENSIONS)
    return "low" if any_decisive else "high"


def backfill_pairwise_confidence() -> dict[str, int]:
    """把历史 done 对比的 verdict.confidence 与 summary 按新「换序稳健」口径重算。幂等。"""
    changed_verdicts = 0
    touched_comps = 0
    with session_scope() as session:
        comps = (
            session.execute(
                select(PairwiseComparison).where(PairwiseComparison.status == "done")
            )
            .scalars()
            .all()
        )
        for comp in comps:
            rows: list[dict[str, Any]] = []
            comp_changed = False
            for v in comp.verdicts:
                new_conf = _derive_confidence(
                    v.winner, v.swap_consistent, v.dimension_winners
                )
                if new_conf != v.confidence:
                    v.confidence = new_conf
                    changed_verdicts += 1
                    comp_changed = True
                rows.append(
                    {
                        "sample_id": v.sample_id,
                        "winner": v.winner,
                        "confidence": v.confidence,
                        "swap_consistent": v.swap_consistent,
                        "dimension_winners": v.dimension_winners,
                        "reason": v.reason,
                    }
                )
            new_summary = _summarize(rows)
            if new_summary != comp.summary:
                comp.summary = new_summary
                comp_changed = True
            if comp_changed:
                touched_comps += 1
    return {"comparisons": touched_comps, "verdicts": changed_verdicts}


def backfill_pairwise_display() -> dict[str, int]:
    """回填历史 done 对比的展示字段：用例 scenario + 决定性 verdict 的理由 A/B 化。幂等。

    - scenario：从两个 run 的 detail_json 取用例场景（B 优先、A 兜底），免再查库。
    """
    filled_scenario = 0
    with session_scope() as session:
        comps = (
            session.execute(
                select(PairwiseComparison).where(PairwiseComparison.status == "done")
            )
            .scalars()
            .all()
        )
        for comp in comps:
            map_a = _detail_map(session, comp.run_a_id)
            map_b = _detail_map(session, comp.run_b_id)
            for v in comp.verdicts:
                if not (v.scenario or "").strip() or not (v.sub_scenario or "").strip():
                    src = map_b.get(v.sample_id) or map_a.get(v.sample_id) or {}
                    case = (src.get("detail") or {}).get("case") or {}
                    scenario = (case.get("scenario") or "").strip()
                    sub_scenario = (case.get("sub_scenario") or "").strip()
                    if scenario and not (v.scenario or "").strip():
                        v.scenario = scenario
                        filled_scenario += 1
                    if sub_scenario and not (v.sub_scenario or "").strip():
                        v.sub_scenario = sub_scenario
    return {"scenario_filled": filled_scenario}


def _summarize(verdicts: list[dict[str, Any]]) -> dict[str, Any]:
    """按有效值汇总（verdicts 每项须含 winner / dimension_winners / confidence_kind）。"""
    a_wins = sum(1 for v in verdicts if v["winner"] == "A")
    b_wins = sum(1 for v in verdicts if v["winner"] == "B")
    ties = sum(1 for v in verdicts if v["winner"] == "tie")
    order_sensitive = sum(1 for v in verdicts if v.get("confidence_kind") == "order")
    safety_doubt = sum(1 for v in verdicts if v.get("confidence_kind") == "safety")
    human_calibrated = sum(1 for v in verdicts if v.get("confidence_kind") == "human")
    low_conf = order_sensitive + safety_doubt
    total = len(verdicts)

    by_dim: dict[str, dict[str, int]] = {
        d: {"A": 0, "B": 0, "tie": 0} for d in _DIMENSIONS
    }
    for v in verdicts:
        dw = v.get("dimension_winners") or {}
        for d in _DIMENSIONS:
            side = dw.get(d, "tie")
            by_dim[d][side if side in ("A", "B") else "tie"] += 1

    overall = "tie"
    if b_wins > a_wins:
        overall = "B"
    elif a_wins > b_wins:
        overall = "A"

    return {
        "total": total,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "ties": ties,
        "low_confidence": low_conf,
        "order_sensitive_count": order_sensitive,
        "safety_doubt_count": safety_doubt,
        "human_calibrated_count": human_calibrated,
        "b_win_rate": (b_wins / total) if total else 0.0,
        "overall_winner": overall,
        "by_dimension": by_dim,
        "regressions": [v["sample_id"] for v in verdicts if v["winner"] == "A"],
        "improvements": [v["sample_id"] for v in verdicts if v["winner"] == "B"],
    }


def pairwise_verdict_to_out(v: PairwiseCaseVerdict):
    """ORM → API 有效值（避免 from_attributes 直出机器字段）。"""
    from .schemas import PairwiseCaseVerdictOut

    eff = verdict_effective_row(v)
    payload: dict[str, Any] = {
        "sample_id": v.sample_id,
        "scenario": v.scenario or "",
        "sub_scenario": v.sub_scenario or "",
        "winner": eff["winner"],
        "confidence_kind": eff["confidence_kind"],
        "human_calibrated": bool(v.human_calibrated),
        "swap_consistent": v.swap_consistent,
        "dimension_winners": eff["dimension_winners"],
        "reason": eff["reason"],
        "order_runs": list(v.order_runs or []),
        "confidence": v.confidence,
    }
    if v.human_calibrated:
        payload["auto_winner"] = v.winner
        payload["auto_confidence"] = v.confidence
        payload["auto_dimension_winners"] = dict(v.dimension_winners or {})
        payload["auto_reason"] = v.reason or ""
    return PairwiseCaseVerdictOut(**payload)


def recompute_pairwise_summary(session, comparison_id: int) -> dict[str, Any]:
    """按当前有效值重算并写回 comparison.summary。"""
    comp = session.get(PairwiseComparison, comparison_id)
    if comp is None:
        raise ValueError(f"对比 {comparison_id} 不存在")
    verdicts = session.execute(
        select(PairwiseCaseVerdict).where(
            PairwiseCaseVerdict.comparison_id == comparison_id
        )
    ).scalars().all()
    rows = [verdict_effective_row(v) for v in verdicts]
    summary = _summarize(rows)
    comp.summary = summary
    session.flush()
    return summary


async def run_pairwise_comparison(comparison_id: int, judge_model_id: int) -> None:
    """后台执行：逐题 PK → 落 PairwiseCaseVerdict → 汇总 → 置 done/failed。"""
    from medeval.models import ConversationTrace, TestCase

    try:
        with session_scope() as session:
            comp = session.get(PairwiseComparison, comparison_id)
            if comp is None:
                return
            run_a_id, run_b_id = comp.run_a_id, comp.run_b_id
            scope = comp.scope or "all"
            map_a = _detail_map(session, run_a_id)
            map_b = _detail_map(session, run_b_id)

        comparator, model_label, concurrency = _build_comparator(judge_model_id)
        with session_scope() as session:
            comp = session.get(PairwiseComparison, comparison_id)
            comp.judge_fingerprint = comparator.fingerprint()

        common = sorted(set(map_a) & set(map_b))
        if scope == "divergent_only":
            common = [
                sid
                for sid in common
                if map_a[sid]["release_passed"] != map_b[sid]["release_passed"]
            ]
        with session_scope() as session:
            comp = session.get(PairwiseComparison, comparison_id)
            comp.total_cases = len(common)

        # 题间并发：LLM 调用并发跑，DB 写在锁内串行（SQLite 单写 + done_cases 原子递增）。
        verdicts: list[dict[str, Any]] = []
        sem = asyncio.Semaphore(concurrency)
        db_lock = asyncio.Lock()

        async def _compare_one(sid: str) -> None:
            detail_a = map_a[sid]["detail"]
            detail_b = map_b[sid]["detail"]
            try:
                case = TestCase.model_validate(detail_a.get("case") or {})
            except Exception:
                case = None
            trace_a = ConversationTrace.model_validate(
                detail_a.get("trace") or {"messages": []}
            )
            trace_b = ConversationTrace.model_validate(
                detail_b.get("trace") or {"messages": []}
            )
            if case is None:
                # 无法重建用例时退化：用空场景仍可对比文本
                case = TestCase(
                    sample_id=sid, scenario="", level="L2",
                    turns=[{"role": "user", "content": ""}],
                )
            async with sem:
                res = await comparator.compare_case(case, trace_a, trace_b)
            row = {
                "sample_id": sid,
                "scenario": (case.scenario or "").strip(),
                "sub_scenario": (case.sub_scenario or "").strip(),
                "winner": res.winner,
                "confidence": res.confidence,
                "swap_consistent": res.swap_consistent,
                "dimension_winners": res.dimension_winners,
                "reason": res.reason,
                "order_runs": res.order_runs,
            }
            # 临界区：写 verdict + 递增进度串行化，避免并发写冲突 / 进度跳变。
            async with db_lock:
                verdicts.append(row)
                with session_scope() as session:
                    session.add(
                        PairwiseCaseVerdict(comparison_id=comparison_id, **row)
                    )
                    comp = session.get(PairwiseComparison, comparison_id)
                    comp.done_cases = len(verdicts)

        await asyncio.gather(*(_compare_one(sid) for sid in common))

        with session_scope() as session:
            recompute_pairwise_summary(session, comparison_id)
            comp = session.get(PairwiseComparison, comparison_id)
            if model_label:
                comp.judge_model = model_label
            comp.status = "done"
            comp.finished_at = datetime.utcnow()
    except Exception as exc:  # noqa: BLE001 —— 失败兜底落 error_msg
        log.exception("pairwise comparison %s failed", comparison_id)
        with session_scope() as session:
            comp = session.get(PairwiseComparison, comparison_id)
            if comp is not None:
                comp.status = "failed"
                comp.error_msg = PAIRWISE_JOB_USER_ERROR
                comp.finished_at = datetime.utcnow()
