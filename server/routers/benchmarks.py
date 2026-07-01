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
    create_uploaded_benchmark_from_feishu_url,
    derive_benchmark_from_yaml,
    derive_benchmark_with_overrides,
    overwrite_benchmark_from_yaml,
    replace_uploaded_benchmark,
    replace_uploaded_benchmark_from_feishu_url,
)
from ..constants import LIST_LIMIT_DEFAULT, LIST_LIMIT_MAX
from ..db import get_session
from .. import feishu_media
from ..models_db import Benchmark, FeishuUser
from ..schemas import (
    BenchmarkCaseYamlIn,
    BenchmarkCaseYamlOut,
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
    file: UploadFile | None = File(None),
    name: str = Form(...),
    description: str = Form(""),
    version: str = Form("v1"),
    source: str = Form("offline"),
    source_url: str = Form(""),
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> Benchmark:
    try:
        if source == "online" and source_url.strip():
            if current_user is None or not current_user.access_token:
                raise HTTPException(status_code=401, detail="请先登录飞书后导入飞书 URL")
            bm = create_uploaded_benchmark_from_feishu_url(
                session,
                name=name,
                source_url=source_url,
                access_token=current_user.access_token,
                description=description,
                version=version,
                created_by=current_user.name if current_user else None,
            )
        else:
            if file is None:
                raise HTTPException(status_code=422, detail="请选择用例文件或填写飞书 URL")
            content = bm_svc.read_upload_capped(file)
            bm = create_uploaded_benchmark(
                session,
                name=name,
                content=content,
                filename=file.filename or "cases.yaml",
                description=description,
                version=version,
                source=source,
                created_by=current_user.name if current_user else None,
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
            created_by=current_user.name if current_user else None,
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
            created_by=current_user.name if current_user else None,
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
    file: UploadFile | None = File(None),
    source: str = Form("offline"),
    source_url: str = Form(""),
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> Benchmark:
    bm = bm_svc.get_benchmark_or_404(session, benchmark_id)
    if bm.source == "builtin":
        raise HTTPException(status_code=400, detail="内置 benchmark 不可覆盖")
    try:
        if source == "online" and source_url.strip():
            if current_user is None or not current_user.access_token:
                raise HTTPException(status_code=401, detail="请先登录飞书后导入飞书 URL")
            replace_uploaded_benchmark_from_feishu_url(
                session,
                bm,
                source_url=source_url,
                access_token=current_user.access_token,
            )
        else:
            if file is None:
                raise HTTPException(status_code=422, detail="请选择用例文件或填写飞书 URL")
            content = bm_svc.read_upload_capped(file)
            replace_uploaded_benchmark(
                session,
                bm,
                content=content,
                filename=file.filename or "cases.yaml",
                source=source,
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


@router.get("/feishu-images/{image_token}")
def get_feishu_image(
    image_token: str,
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> Response:
    if current_user is None or not current_user.access_token:
        raise HTTPException(status_code=401, detail="请先登录飞书后查看图片")
    try:
        media = feishu_media.fetch_media(current_user.access_token, image_token)
    except feishu_media.FeishuMediaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=media.content,
        media_type=media.content_type,
        headers={"Cache-Control": "private, max-age=3600"},
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


@router.get("/{benchmark_id}/cases/{sample_id}/yaml", response_model=BenchmarkCaseYamlOut)
def get_benchmark_case_yaml(
    benchmark_id: int, sample_id: str, session: Session = Depends(get_session)
) -> BenchmarkCaseYamlOut:
    return bm_svc.get_benchmark_case_yaml(session, benchmark_id, sample_id)


@router.put("/{benchmark_id}/cases/{sample_id}/yaml", response_model=BenchmarkCaseYamlOut)
def save_benchmark_case_yaml(
    benchmark_id: int,
    sample_id: str,
    payload: BenchmarkCaseYamlIn,
    session: Session = Depends(get_session),
) -> BenchmarkCaseYamlOut:
    return bm_svc.save_benchmark_case_yaml(session, benchmark_id, sample_id, payload)


@router.delete("/{benchmark_id}", status_code=204)
def delete_benchmark(
    benchmark_id: int, session: Session = Depends(get_session)
) -> None:
    bm_svc.delete_benchmark(session, benchmark_id)
