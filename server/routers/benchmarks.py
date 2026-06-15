"""benchmark 路由：上传 / 列表 / 详情 / 用例清单 / 删除。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..benchmarks import (
    BenchmarkValidationError,
    create_uploaded_benchmark,
    derive_benchmark_from_yaml,
    derive_benchmark_with_overrides,
    ensure_builtin_benchmark,
    export_benchmark_yaml,
    load_benchmark_cases,
    overwrite_benchmark_from_yaml,
    replace_uploaded_benchmark,
)
from ..db import get_session
from ..deps import creator_name
from ..models_db import Benchmark, FeishuUser
from ..schemas import (
    BenchmarkOut,
    BenchmarkUpdateRequest,
    CaseBrief,
    DeriveBenchmarkRequest,
    DeriveBenchmarkYamlRequest,
    OverwriteBenchmarkYamlRequest,
)
from ..settings import get_settings

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


def _read_upload_capped(file: UploadFile) -> bytes:
    """读取上传文件，超过配置上限即拒绝（避免超大上传打爆内存）。"""
    limit = get_settings().max_upload_bytes
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"上传文件超过大小上限（{limit} 字节）",
        )
    return content


def _get_or_404(session: Session, benchmark_id: int) -> Benchmark:
    bm = session.get(Benchmark, benchmark_id)
    if bm is None:
        raise HTTPException(status_code=404, detail=f"benchmark {benchmark_id} 不存在")
    return bm


@router.get("", response_model=list[BenchmarkOut])
def list_benchmarks(session: Session = Depends(get_session)) -> list[Benchmark]:
    ensure_builtin_benchmark(session)
    return list(
        session.execute(select(Benchmark).order_by(Benchmark.id)).scalars().all()
    )


@router.post("", response_model=BenchmarkOut, status_code=201)
def upload_benchmark(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    version: str = Form("v1"),
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> Benchmark:
    content = _read_upload_capped(file)
    try:
        bm = create_uploaded_benchmark(
            session,
            name=name,
            content=content,
            filename=file.filename or "cases.yaml",
            description=description,
            version=version,
            created_by=creator_name(current_user),
        )
    except BenchmarkValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return bm


@router.post("/{benchmark_id}/derive", response_model=BenchmarkOut, status_code=201)
def derive_benchmark(
    benchmark_id: int,
    payload: DeriveBenchmarkRequest,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> Benchmark:
    """基于源 benchmark 改若干用例判据，另存为一个新的 uploaded benchmark（不动源）。"""
    src = _get_or_404(session, benchmark_id)
    try:
        bm = derive_benchmark_with_overrides(
            session,
            src,
            name=payload.name,
            description=payload.description,
            case_overrides=[o.model_dump(exclude_none=True) for o in payload.case_overrides],
            created_by=creator_name(current_user),
        )
    except BenchmarkValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return bm


@router.post("/{benchmark_id}/derive-yaml", response_model=BenchmarkOut, status_code=201)
def derive_benchmark_yaml(
    benchmark_id: int,
    payload: DeriveBenchmarkYamlRequest,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> Benchmark:
    """从整段用例 YAML 改判据，另存为新 benchmark（按 sample_id 只合并判据字段、未匹配丢弃）。"""
    src = _get_or_404(session, benchmark_id)
    try:
        bm = derive_benchmark_from_yaml(
            session,
            src,
            name=payload.name,
            yaml_text=payload.yaml_text,
            description=payload.description,
            created_by=creator_name(current_user),
        )
    except BenchmarkValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return bm


@router.post("/{benchmark_id}/overwrite-yaml", response_model=BenchmarkOut)
def overwrite_benchmark_yaml(
    benchmark_id: int,
    payload: OverwriteBenchmarkYamlRequest,
    session: Session = Depends(get_session),
) -> Benchmark:
    """从整段用例 YAML 改判据，就地覆盖原 benchmark（合并语义同另存；内置不可覆盖）。"""
    bm = _get_or_404(session, benchmark_id)
    if bm.source == "builtin":
        raise HTTPException(status_code=400, detail="内置 benchmark 不可覆盖")
    try:
        overwrite_benchmark_from_yaml(session, bm, yaml_text=payload.yaml_text)
    except BenchmarkValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return bm


@router.patch("/{benchmark_id}", response_model=BenchmarkOut)
def update_benchmark(
    benchmark_id: int,
    payload: BenchmarkUpdateRequest,
    session: Session = Depends(get_session),
) -> Benchmark:
    """修改 benchmark 名称/描述（仅上传项可改，不动用例内容与判据）。"""
    bm = _get_or_404(session, benchmark_id)
    if bm.source == "builtin":
        raise HTTPException(status_code=400, detail="内置 benchmark 不可编辑")
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="名称不能为空")
        bm.name = name
    if payload.description is not None:
        bm.description = payload.description
    return bm


@router.put("/{benchmark_id}", response_model=BenchmarkOut)
def replace_benchmark(
    benchmark_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> Benchmark:
    """用新 YAML 覆盖一个已上传的 benchmark（下载→修改→重传闭环）。"""
    bm = _get_or_404(session, benchmark_id)
    if bm.source == "builtin":
        raise HTTPException(status_code=400, detail="内置 benchmark 不可覆盖")
    content = _read_upload_capped(file)
    try:
        replace_uploaded_benchmark(
            session, bm, content=content, filename=file.filename or "cases.yaml"
        )
    except BenchmarkValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return bm


@router.get("/{benchmark_id}/download")
def download_benchmark(
    benchmark_id: int, session: Session = Depends(get_session)
) -> Response:
    bm = _get_or_404(session, benchmark_id)
    filename, text = export_benchmark_yaml(bm)
    return Response(
        content=text,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{benchmark_id}", response_model=BenchmarkOut)
def get_benchmark(
    benchmark_id: int, session: Session = Depends(get_session)
) -> Benchmark:
    return _get_or_404(session, benchmark_id)


@router.get("/{benchmark_id}/cases", response_model=list[CaseBrief])
def list_benchmark_cases(
    benchmark_id: int, session: Session = Depends(get_session)
) -> list[CaseBrief]:
    bm = _get_or_404(session, benchmark_id)
    cases = load_benchmark_cases(bm)
    return [
        CaseBrief(
            sample_id=c.sample_id,
            scenario=c.scenario,
            sub_scenario=c.sub_scenario,
            level=getattr(c.level, "value", c.level),
            score_profile=getattr(c.score_profile, "value", c.score_profile),
        )
        for c in cases
    ]


@router.delete("/{benchmark_id}", status_code=204)
def delete_benchmark(
    benchmark_id: int, session: Session = Depends(get_session)
) -> None:
    bm = _get_or_404(session, benchmark_id)
    if bm.source == "builtin":
        raise HTTPException(status_code=400, detail="内置 benchmark 不可删除")
    # 删除上传的用例目录（限定在 uploads 目录内，避免误删）
    uploads_root = get_settings().uploads_dir.resolve()
    storage = Path(bm.storage_path).resolve()
    if bm.storage_path and uploads_root in storage.parents:
        shutil.rmtree(storage, ignore_errors=True)
    session.delete(bm)
