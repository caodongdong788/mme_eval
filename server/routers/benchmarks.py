"""benchmark 路由：上传 / 列表 / 详情 / 用例清单 / 删除。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..benchmarks import (
    BenchmarkValidationError,
    create_uploaded_benchmark,
    derive_benchmark_from_yaml,
    derive_benchmark_with_overrides,
    overwrite_benchmark_from_yaml,
    replace_uploaded_benchmark,
)
from ..constants import LIST_LIMIT_DEFAULT, LIST_LIMIT_MAX
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
from ..services import benchmark_catalog as bm_svc

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


@router.get("", response_model=list[BenchmarkOut])
def list_benchmarks(
    limit: int = Query(
        LIST_LIMIT_DEFAULT, ge=1, le=LIST_LIMIT_MAX, description="分页大小"
    ),
    offset: int = Query(0, ge=0, description="分页偏移"),
    session: Session = Depends(get_session),
) -> list[Benchmark]:
    rows = bm_svc.list_benchmarks(session)
    return rows[offset : offset + limit]


@router.post("", response_model=BenchmarkOut, status_code=201)
def upload_benchmark(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    version: str = Form("v1"),
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> Benchmark:
    content = bm_svc.read_upload_capped(file)
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
    src = bm_svc.get_benchmark_or_404(session, benchmark_id)
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
    src = bm_svc.get_benchmark_or_404(session, benchmark_id)
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
    bm = bm_svc.get_benchmark_or_404(session, benchmark_id)
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
    return bm_svc.update_benchmark(session, benchmark_id, payload)


@router.put("/{benchmark_id}", response_model=BenchmarkOut)
def replace_benchmark(
    benchmark_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> Benchmark:
    bm = bm_svc.get_benchmark_or_404(session, benchmark_id)
    if bm.source == "builtin":
        raise HTTPException(status_code=400, detail="内置 benchmark 不可覆盖")
    content = bm_svc.read_upload_capped(file)
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
    filename, text = bm_svc.export_download(benchmark_id, session)
    return Response(
        content=text,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{benchmark_id}", response_model=BenchmarkOut)
def get_benchmark(
    benchmark_id: int, session: Session = Depends(get_session)
) -> Benchmark:
    return bm_svc.get_benchmark_or_404(session, benchmark_id)


@router.get("/{benchmark_id}/cases", response_model=list[CaseBrief])
def list_benchmark_cases(
    benchmark_id: int, session: Session = Depends(get_session)
) -> list[CaseBrief]:
    return bm_svc.list_benchmark_case_briefs(session, benchmark_id)


@router.delete("/{benchmark_id}", status_code=204)
def delete_benchmark(
    benchmark_id: int, session: Session = Depends(get_session)
) -> None:
    bm_svc.delete_benchmark(session, benchmark_id)
