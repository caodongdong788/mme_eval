"""线上标注池路由。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..db import get_session
from ..models_db import FeishuUser, OnlineAnnotationPoolCase, OnlineAnnotationPoolPath
from ..schemas import (
    OnlineAnnotationPoolCaseAdd,
    OnlineAnnotationPoolCaseOut,
    OnlineAnnotationPoolFeishuImport,
    OnlineAnnotationPoolPathCreate,
    OnlineAnnotationPoolPathOut,
    OnlineAnnotationPoolPathUpdate,
    OnlineEvalExportOut,
)
from ..services import online_annotation_pool as svc

router = APIRouter(prefix="/api/online-annotation-pool", tags=["online-annotation-pool"])


@router.get("/paths", response_model=list[OnlineAnnotationPoolPathOut])
def list_pool_paths(session: Session = Depends(get_session)) -> list[OnlineAnnotationPoolPath]:
    return svc.list_paths(session)


@router.post("/paths", response_model=OnlineAnnotationPoolPathOut, status_code=201)
def create_pool_path(
    payload: OnlineAnnotationPoolPathCreate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> OnlineAnnotationPoolPath:
    return svc.create_path(
        session,
        path=payload.path,
        description=payload.description,
        created_by=current_user.name if current_user else None,
    )


@router.post("/paths/import-feishu", response_model=OnlineAnnotationPoolPathOut, status_code=201)
def import_pool_path_from_feishu(
    payload: OnlineAnnotationPoolFeishuImport,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> OnlineAnnotationPoolPath:
    return svc.import_path_from_feishu_url(
        session,
        path=payload.path,
        description=payload.description,
        source_url=payload.source_url,
        current_user=current_user,
    )


@router.patch("/paths/{path_id}", response_model=OnlineAnnotationPoolPathOut)
def update_pool_path(
    path_id: int,
    payload: OnlineAnnotationPoolPathUpdate,
    session: Session = Depends(get_session),
) -> OnlineAnnotationPoolPath:
    return svc.update_path(
        session,
        path_id,
        path=payload.path,
        description=payload.description,
    )


@router.delete("/paths/{path_id}", status_code=204)
def delete_pool_path(
    path_id: int,
    session: Session = Depends(get_session),
) -> None:
    svc.delete_path(session, path_id)


@router.get("/paths/{path_id}/cases", response_model=list[OnlineAnnotationPoolCaseOut])
def list_pool_cases(
    path_id: int,
    session: Session = Depends(get_session),
) -> list[OnlineAnnotationPoolCase]:
    return svc.list_cases(session, path_id)


@router.post("/paths/{path_id}/cases", response_model=OnlineAnnotationPoolCaseOut, status_code=201)
def add_pool_case(
    path_id: int,
    payload: OnlineAnnotationPoolCaseAdd,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> OnlineAnnotationPoolCase:
    return svc.add_case(
        session,
        path_id=path_id,
        online_eval_case_id=payload.online_eval_case_id,
        created_by=current_user.name if current_user else None,
    )


@router.delete("/paths/{path_id}/cases/{case_id}", status_code=204)
def delete_pool_case(
    path_id: int,
    case_id: int,
    session: Session = Depends(get_session),
) -> None:
    svc.delete_case(session, path_id, case_id)


@router.post("/paths/{path_id}/export-cases", response_model=OnlineEvalExportOut)
def export_pool_cases(
    path_id: int,
    parent_folder_token: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> dict[str, Any]:
    return svc.export_path_cases(
        session,
        path_id,
        parent_folder_token=parent_folder_token,
        current_user=current_user,
    )
