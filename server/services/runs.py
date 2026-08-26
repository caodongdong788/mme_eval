"""Run 域服务：查询、产物路径、派生 run 创建、CRUD。"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from medeval import retention

from ..compare import compare_runs
from ..constants import LIST_LIMIT_DEFAULT
from ..models_db import (
    Benchmark,
    CaseAnnotation,
    CaseResultRow,
    EvalRun,
    JudgeModelConfig,
    PairwiseComparison,
)
from ..paths import safe_join
from ..schemas import JudgeOverride, RunCreate, RunRenameRequest
from ..settings import get_settings
from .attribution_summary import cx_agent_optimization_counts
from . import judge_models as judge_models_svc


def get_run_or_404(session: Session, run_id: int) -> EvalRun:
    run = session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} 不存在")
    return run


def release_gate(
    session: Session,
    run_id: int,
    baseline_run_id: int,
    *,
    max_pass_rate_drop: float = 0.0,
    max_regressions: int = 0,
) -> dict[str, Any]:
    """回归门禁：只比较同 sample_id 的真实 Case 结果，输出可被 CI 直接消费的 JSON。"""
    current = get_run_or_404(session, run_id)
    baseline = get_run_or_404(session, baseline_run_id)
    if current.status != "success" or baseline.status != "success":
        raise HTTPException(status_code=422, detail="仅已完成的 run 可做发布门禁")
    current_rows = session.execute(select(CaseResultRow).where(CaseResultRow.run_id == run_id)).scalars().all()
    baseline_rows = session.execute(select(CaseResultRow).where(CaseResultRow.run_id == baseline_run_id)).scalars().all()
    now = {row.sample_id: row for row in current_rows}
    before = {row.sample_id: row for row in baseline_rows}
    shared = sorted(set(now) & set(before))
    regressions = [sample_id for sample_id in shared if before[sample_id].release_passed and not now[sample_id].release_passed]
    improvements = [sample_id for sample_id in shared if not before[sample_id].release_passed and now[sample_id].release_passed]
    pass_rate_drop = float(baseline.pass_rate or 0) - float(current.pass_rate or 0)
    comparable = bool(shared) and not (set(now) - set(before) or set(before) - set(now))
    checks = {
        "same_case_set": comparable,
        "pass_rate_drop": pass_rate_drop <= max_pass_rate_drop,
        "regressions": len(regressions) <= max_regressions,
        "medical_safety": current.medical_safety_failed <= baseline.medical_safety_failed,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "current_run_id": current.id,
        "baseline_run_id": baseline.id,
        "case_count": len(shared),
        "new_cases": sorted(set(now) - set(before)),
        "missing_cases": sorted(set(before) - set(now)),
        "regressions": regressions,
        "improvements": improvements,
        "pass_rate_drop": pass_rate_drop,
        "thresholds": {"max_pass_rate_drop": max_pass_rate_drop, "max_regressions": max_regressions},
        "reliability": (current.grading or {}).get("reliability", {}),
    }


def source_out_dir(run: EvalRun) -> Optional[Path]:
    """源 run 的产物目录（经 safe_join 限定在 outputs 根目录内）。slug 缺失/越界返回 None。"""
    slug = run.run_slug
    if not slug or slug == "(pending)":
        return None
    try:
        return safe_join(get_settings().outputs_dir, slug)
    except ValueError:
        return None


def create_derived_run(
    session: Session,
    source: EvalRun,
    *,
    suffix: str,
    extra_judge_overrides: Optional[dict[str, Any]] = None,
    created_by: Optional[str] = None,
) -> EvalRun:
    """为重判/续跑新建一行 pending EvalRun，沿用源 run 的 benchmark/覆盖/n_runs。"""
    base = source.name or source.run_slug
    name = f"{base} · {suffix} {datetime.now().strftime('%m%d-%H%M%S')}"
    judge_overrides = dict(source.judge_overrides or {})
    if extra_judge_overrides:
        judge_overrides.update(extra_judge_overrides)
    derived = EvalRun(
        run_slug="(pending)",
        name=name,
        status="pending",
        scoring_standard=source.scoring_standard or "cx_eight_dimension",
        benchmark_id=source.benchmark_id,
        judge_overrides=judge_overrides,
        adapter_overrides=dict(source.adapter_overrides or {}),
        n_runs=source.n_runs or 1,
        parent_run_id=source.id,
        created_by=created_by,
    )
    session.add(derived)
    session.flush()
    return derived


@dataclass
class CreateRunPlan:
    """新建评测落库结果 + 提交 eval job 所需参数。"""

    run: EvalRun
    benchmark_id: int
    run_name: Optional[str]
    levels: Optional[list[str]]
    limit: Optional[int]
    repeat: Optional[int]
    judge_full: Optional[dict[str, Any]]
    adapter_full: Optional[dict[str, Any]]
    judge_model_id: Optional[int]
    user_simulator_model_id: Optional[int]


def prepare_create_run(
    session: Session,
    payload: RunCreate,
    *,
    created_by: Optional[str] = None,
    trigger_type: str = "manual",
    scheduled_evaluation_id: int | None = None,
    scheduled_occurrence_key: str | None = None,
    open_api_key_id: int | None = None,
) -> CreateRunPlan:
    # 独立 Worker 不能安全继承请求进程内的一次性明文密钥。持久化模式要求使用
    # 已保存的模型配置或环境变量，避免把凭据写进数据库队列。
    if get_settings().job_runner_mode == "database":
        if payload.adapter is not None and payload.adapter.api_key:
            raise HTTPException(
                status_code=422,
                detail="持久化评测不支持一次性 Adapter API Key，请改用服务端环境变量",
            )
        if payload.judge is not None and payload.judge.api_key and payload.judge_model_id is None:
            raise HTTPException(
                status_code=422,
                detail="持久化评测不支持一次性 Judge API Key，请先保存判分模型后再选择",
            )
        if (
            payload.user_simulator is not None
            and payload.user_simulator.api_key
            and payload.user_simulator_model_id is None
        ):
            raise HTTPException(
                status_code=422,
                detail="持久化评测不支持一次性追问模型 API Key，请先保存模型后再选择",
            )
    bm = session.get(Benchmark, payload.benchmark_id)
    if bm is None:
        raise HTTPException(
            status_code=404, detail=f"benchmark {payload.benchmark_id} 不存在"
        )

    final_name = payload.run_name or bm.name
    exists = session.execute(
        select(EvalRun.id).where(EvalRun.name == final_name)
    ).first()
    if exists is not None:
        raise HTTPException(
            status_code=409, detail=f"评测名称「{final_name}」已存在，请换一个名称"
        )

    judge_ov = payload.judge or JudgeOverride()
    if payload.judge_model_id is not None:
        jm = session.get(JudgeModelConfig, payload.judge_model_id)
        if jm is None:
            raise HTTPException(
                status_code=404, detail=f"判分模型 {payload.judge_model_id} 不存在"
            )
        if judge_ov.enabled is not False and not judge_models_svc.has_judge_model_api_key(jm):
            raise HTTPException(
                status_code=422,
                detail=f"判分模型「{jm.name}」未配置可用的 API Key",
            )
        judge_ov = JudgeOverride(
            enabled=judge_ov.enabled,
            provider=jm.provider or None,
            model=jm.model or None,
            base_url=jm.base_url or None,
            api_version=jm.api_version or None,
            api_key=jm.api_key or None,
            temperature=jm.temperature,
            enable_thinking=jm.enable_thinking,
        )
    has_judge = payload.judge is not None or payload.judge_model_id is not None
    judge_public = judge_ov.public_dict() if has_judge else {}
    if payload.judge_model_id is not None:
        judge_public["__model_id"] = payload.judge_model_id

    simulator_ov = payload.user_simulator or JudgeOverride()
    if payload.user_simulator_model_id is not None:
        simulator_model = session.get(JudgeModelConfig, payload.user_simulator_model_id)
        if simulator_model is None:
            raise HTTPException(
                status_code=404,
                detail=f"语义追问模型 {payload.user_simulator_model_id} 不存在",
            )
        simulator_ov = JudgeOverride(
            enabled=True,
            provider=simulator_model.provider or None,
            model=simulator_model.model or None,
            base_url=simulator_model.base_url or None,
            api_version=simulator_model.api_version or None,
            api_key=simulator_model.api_key or None,
            temperature=simulator_model.temperature,
            enable_thinking=simulator_model.enable_thinking,
        )
    has_simulator = (
        payload.user_simulator is not None or payload.user_simulator_model_id is not None
    )
    # 复用已有 JSON 覆盖字段持久化 Run 级执行模式，避免给已有 SQLite 数据库增加迁移。
    # apply_adapter_overrides 只处理白名单字段，因此该元数据不会传给被测 Agent。
    adapter_public = payload.adapter.public_dict() if payload.adapter else {}
    adapter_public["evaluation_mode"] = payload.evaluation_mode
    if has_simulator:
        simulator_public = simulator_ov.public_dict()
        if payload.user_simulator_model_id is not None:
            simulator_public["__model_id"] = payload.user_simulator_model_id
        adapter_public["user_simulator"] = simulator_public

    run = EvalRun(
        run_slug="(pending)",
        name=final_name,
        status="pending",
        scoring_standard=payload.scoring_standard,
        trigger_type=trigger_type if trigger_type in {"manual", "scheduled", "open_api"} else "manual",
        benchmark_id=bm.id,
        scheduled_evaluation_id=scheduled_evaluation_id if trigger_type == "scheduled" else None,
        scheduled_occurrence_key=(
            scheduled_occurrence_key if trigger_type == "scheduled" else None
        ),
        open_api_key_id=open_api_key_id if trigger_type == "open_api" else None,
        judge_overrides=judge_public,
        adapter_overrides=adapter_public,
        n_runs=payload.repeat or 1,
        created_by=created_by,
    )
    session.add(run)
    session.flush()

    judge_full = judge_ov.model_dump(exclude_none=True) if has_judge else None
    adapter_full = payload.adapter.model_dump(exclude_none=True) if payload.adapter else {}
    adapter_full["evaluation_mode"] = payload.evaluation_mode
    if has_simulator:
        adapter_full["user_simulator"] = simulator_ov.model_dump(exclude_none=True)
    return CreateRunPlan(
        run=run,
        benchmark_id=bm.id,
        run_name=payload.run_name,
        levels=payload.levels,
        limit=payload.limit,
        repeat=payload.repeat,
        judge_full=judge_full,
        adapter_full=adapter_full,
        judge_model_id=payload.judge_model_id,
        user_simulator_model_id=payload.user_simulator_model_id,
    )


def list_runs(
    session: Session,
    *,
    benchmark_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> list[EvalRun]:
    effective_limit = LIST_LIMIT_DEFAULT if limit is None else limit
    stmt = select(EvalRun).order_by(EvalRun.id.desc())
    if benchmark_id is not None:
        stmt = stmt.where(EvalRun.benchmark_id == benchmark_id)
    if offset:
        stmt = stmt.offset(offset)
    stmt = stmt.limit(effective_limit)
    runs = list(session.execute(stmt).scalars().all())
    _attach_benchmark_names(session, runs)
    _attach_cx_agent_optimization_counts(session, runs)
    return runs


def _attach_benchmark_names(session: Session, runs: list[EvalRun]) -> None:
    benchmark_ids = {run.benchmark_id for run in runs if run.benchmark_id is not None}
    names = (
        dict(
            session.execute(
                select(Benchmark.id, Benchmark.name).where(Benchmark.id.in_(benchmark_ids))
            ).all()
        )
        if benchmark_ids
        else {}
    )
    for run in runs:
        setattr(run, "benchmark_name", names.get(run.benchmark_id))


def _attach_cx_agent_optimization_counts(session: Session, runs: list[EvalRun]) -> None:
    """从 Run 的轻量归因摘要补充首页趋势计数。

    归因明细中的完整证据包可能很大，列表页不能再为近 50 条 Run 扫描和解析它。
    摘要会在归因任务终态时更新；历史数据按需访问归因页后也会补齐。
    """
    for run in runs:
        counts = cx_agent_optimization_counts(run.attribution_summary)
        if counts is None:
            setattr(run, "cx_agent_optimization_count", None)
            setattr(run, "cx_agent_p0_optimization_count", None)
            continue
        total, p0_total = counts
        setattr(run, "cx_agent_optimization_count", total)
        setattr(run, "cx_agent_p0_optimization_count", p0_total)


def delete_run(session: Session, run_id: int) -> None:
    run = get_run_or_404(session, run_id)
    # 旁路表 / 对比表无 ORM cascade，须先清以免 FK 约束导致 commit 失败（Postgres / FK=ON 的 SQLite）。
    for comp in session.execute(
        select(PairwiseComparison).where(
            or_(
                PairwiseComparison.run_a_id == run_id,
                PairwiseComparison.run_b_id == run_id,
            )
        )
    ).scalars():
        session.delete(comp)
    session.execute(delete(CaseAnnotation).where(CaseAnnotation.run_id == run_id))

    run_slug = run.run_slug
    if run_slug and run_slug != "(pending)":
        out_dir = source_out_dir(run)
        if out_dir is not None:
            shutil.rmtree(out_dir, ignore_errors=True)
    session.delete(run)


def rename_run(session: Session, run_id: int, payload: RunRenameRequest) -> EvalRun:
    run = get_run_or_404(session, run_id)
    new_name = (payload.name or "").strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="评测名称不能为空")
    dup = session.execute(
        select(EvalRun.id).where(EvalRun.name == new_name, EvalRun.id != run_id)
    ).first()
    if dup is not None:
        raise HTTPException(
            status_code=409, detail=f"评测名称「{new_name}」已存在，请换一个名称"
        )
    run.name = new_name
    return run


def set_run_pinned(session: Session, run_id: int, pinned: bool) -> dict[str, Any]:
    run = get_run_or_404(session, run_id)
    run.pinned = pinned
    out_dir = source_out_dir(run)
    if out_dir is not None and out_dir.is_dir():
        sentinel = out_dir / retention.KEEP_SENTINEL
        try:
            if pinned:
                sentinel.touch()
            elif sentinel.exists():
                sentinel.unlink()
        except OSError:
            pass
    return {"id": run_id, "pinned": pinned}


def diff_runs(session: Session, run_id: int, against_id: int) -> dict[str, Any]:
    current = get_run_or_404(session, run_id)
    base = session.get(EvalRun, against_id)
    if base is None:
        raise HTTPException(status_code=404, detail=f"对比目标 run {against_id} 不存在")
    return compare_runs(session, current, base)
