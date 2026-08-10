"""判分模型配置 CRUD（api_key 只写不读）。"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from medeval.config import load_config

from ..models_db import JudgeModelConfig
from ..schemas import JudgeModelCreate, JudgeModelUpdate
from ..settings import get_settings


def has_judge_model_api_key(row: JudgeModelConfig) -> bool:
    """判断模型是否有可用于评测的凭据，且绝不返回凭据本身。

    自定义模型的 Key 保存在模型记录中；平台默认 DashScope 模型则复用
    ``config.yaml`` 声明的环境变量（通常为 ``LLM_API_KEY``），不能只看
    数据库中的 ``api_key`` 列。
    """
    if row.api_key:
        return True
    try:
        configured = load_config(get_settings().config_path).judges.eight_dimension
    except Exception:  # noqa: BLE001 - 配置不可读时按不可用展示，由实际请求报详情
        return False
    is_configured_connection = (
        (row.provider or "").strip() == (configured.provider or "").strip()
        and (row.model or "").strip() == (configured.model or "").strip()
        and (row.base_url or "").rstrip("/") == (configured.base_url or "").rstrip("/")
        and (row.api_version or "").strip() == (configured.api_version or "").strip()
    )
    return bool(
        is_configured_connection
        and (
            str(configured.api_key or "").strip()
            or os.environ.get(configured.api_key_env or "", "").strip()
        )
    )


def get_judge_model_or_404(session: Session, model_id: int) -> JudgeModelConfig:
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


def list_judge_models(session: Session) -> list[JudgeModelConfig]:
    return list(
        session.execute(select(JudgeModelConfig).order_by(JudgeModelConfig.id)).scalars().all()
    )


def create_judge_model(
    session: Session,
    payload: JudgeModelCreate,
    *,
    created_by: Optional[str],
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
        enable_thinking=payload.enable_thinking,
        pairwise_concurrency=payload.pairwise_concurrency,
        api_key=(payload.api_key or None),
        created_by=created_by,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail=f"判分模型名称「{name}」已存在") from exc
    return row


def update_judge_model(
    session: Session, model_id: int, payload: JudgeModelUpdate
) -> JudgeModelConfig:
    row = get_judge_model_or_404(session, model_id)
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
    if payload.enable_thinking is not None:
        row.enable_thinking = payload.enable_thinking
    if payload.pairwise_concurrency is not None:
        row.pairwise_concurrency = payload.pairwise_concurrency
    if payload.api_key:
        row.api_key = payload.api_key
    session.flush()
    return row


def delete_judge_model(session: Session, model_id: int) -> None:
    row = get_judge_model_or_404(session, model_id)
    session.delete(row)
