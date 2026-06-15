"""判分模型配置路由：全局共享的 LLM-as-Judge 连接配置 CRUD。

api_key 只写不读——读取类接口只回 has_api_key 掩码，发起评测时由服务端读取注入运行期。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..db import get_session
from ..deps import creator_name
from ..models_db import FeishuUser, JudgeModelConfig
from ..schemas import JudgeModelCreate, JudgeModelOut, JudgeModelUpdate

router = APIRouter(prefix="/api/judge-models", tags=["judge-models"])


def _get_or_404(session: Session, model_id: int) -> JudgeModelConfig:
    row = session.get(JudgeModelConfig, model_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"判分模型 {model_id} 不存在")
    return row


def _ensure_name_free(session: Session, name: str, *, exclude_id: Optional[int] = None) -> None:
    stmt = select(JudgeModelConfig.id).where(JudgeModelConfig.name == name)
    if exclude_id is not None:
        stmt = stmt.where(JudgeModelConfig.id != exclude_id)
    if session.execute(stmt).first() is not None:
        raise HTTPException(status_code=409, detail=f"判分模型名称「{name}」已存在")


@router.get("", response_model=list[JudgeModelOut])
def list_judge_models(session: Session = Depends(get_session)) -> list[JudgeModelConfig]:
    return list(
        session.execute(select(JudgeModelConfig).order_by(JudgeModelConfig.id)).scalars().all()
    )


@router.post("", response_model=JudgeModelOut, status_code=201)
def create_judge_model(
    payload: JudgeModelCreate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> JudgeModelConfig:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="名称不能为空")
    if not payload.model.strip():
        raise HTTPException(status_code=422, detail="模型名不能为空")
    _ensure_name_free(session, name)
    row = JudgeModelConfig(
        name=name,
        provider=payload.provider or "openai",
        model=payload.model.strip(),
        base_url=payload.base_url or "",
        api_version=payload.api_version or "",
        temperature=payload.temperature,
        pairwise_concurrency=payload.pairwise_concurrency,
        api_key=(payload.api_key or None),
        created_by=creator_name(current_user),
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:  # 兜底并发撞名
        raise HTTPException(status_code=409, detail=f"判分模型名称「{name}」已存在") from exc
    return row


@router.patch("/{model_id}", response_model=JudgeModelOut)
def update_judge_model(
    model_id: int,
    payload: JudgeModelUpdate,
    session: Session = Depends(get_session),
) -> JudgeModelConfig:
    row = _get_or_404(session, model_id)
    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(status_code=422, detail="名称不能为空")
        _ensure_name_free(session, new_name, exclude_id=model_id)
        row.name = new_name
    if payload.provider is not None:
        row.provider = payload.provider or "openai"
    if payload.model is not None:
        if not payload.model.strip():
            raise HTTPException(status_code=422, detail="模型名不能为空")
        row.model = payload.model.strip()
    if payload.base_url is not None:
        row.base_url = payload.base_url
    if payload.api_version is not None:
        row.api_version = payload.api_version
    if payload.temperature is not None:
        row.temperature = payload.temperature
    if payload.pairwise_concurrency is not None:
        row.pairwise_concurrency = payload.pairwise_concurrency
    # api_key：None=保持不变；非空=覆盖。
    if payload.api_key:
        row.api_key = payload.api_key
    session.flush()
    return row


@router.delete("/{model_id}", status_code=204)
def delete_judge_model(model_id: int, session: Session = Depends(get_session)) -> None:
    row = _get_or_404(session, model_id)
    session.delete(row)
