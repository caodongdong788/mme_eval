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
from ..models_db import Benchmark, CaseAnnotation, EvalRun, JudgeModelConfig, PairwiseComparison
from ..paths import safe_join
from ..schemas import JudgeOverride, RunCreate, RunRenameRequest
from ..settings import get_settings


def get_run_or_404(session: Session, run_id: int) -> EvalRun:
    run = session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} 不存在")
    return run


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
        benchmark_id=source.benchmark_id,
        judge_overrides=judge_overrides,
        adapter_overrides=dict(source.adapter_overrides or {}),
        n_runs=source.n_runs or 1,
        parent_run_id=source.id,
    )
    session.add(derived)
    session.flush()
    session.commit()
    return derived


@dataclass
class CreateRunPlan:
    """新建评测落库结果 + 提交 eval job 所需参数。"""

    run: EvalRun
    benchmark_id: int
    run_name: Optional[str]
    score_profiles: Optional[list[str]]
    levels: Optional[list[str]]
    limit: Optional[int]
    repeat: Optional[int]
    judge_full: Optional[dict[str, Any]]
    adapter_full: Optional[dict[str, Any]]


def prepare_create_run(session: Session, payload: RunCreate) -> CreateRunPlan:
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
        judge_ov = JudgeOverride(
            enabled=judge_ov.enabled,
            provider=jm.provider or None,
            model=jm.model or None,
            base_url=jm.base_url or None,
            api_version=jm.api_version or None,
            api_key=jm.api_key or None,
            temperature=jm.temperature,
            prompt_template=jm.prompt_template or None,
        )
    has_judge = payload.judge is not None or payload.judge_model_id is not None
    judge_public = judge_ov.public_dict() if has_judge else {}
    adapter_public = payload.adapter.public_dict() if payload.adapter else {}

    run = EvalRun(
        run_slug="(pending)",
        name=final_name,
        status="pending",
        benchmark_id=bm.id,
        judge_overrides=judge_public,
        adapter_overrides=adapter_public,
        n_runs=payload.repeat or 1,
    )
    session.add(run)
    session.flush()
    session.commit()

    judge_full = judge_ov.model_dump(exclude_none=True) if has_judge else None
    adapter_full = (
        payload.adapter.model_dump(exclude_none=True) if payload.adapter else None
    )
    return CreateRunPlan(
        run=run,
        benchmark_id=bm.id,
        run_name=payload.run_name,
        score_profiles=payload.score_profiles,
        levels=payload.levels,
        limit=payload.limit,
        repeat=payload.repeat,
        judge_full=judge_full,
        adapter_full=adapter_full,
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
    return list(session.execute(stmt).scalars().all())


def delete_run(session: Session, run_id: int) -> None:
    run = get_run_or_404(session, run_id)
    if run.status in ("running", "pending"):
        raise HTTPException(
            status_code=400, detail="运行中或等待中的评测不可删除，请等待完成"
        )
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
