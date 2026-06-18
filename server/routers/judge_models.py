"""判分模型配置路由：全局共享的 LLM-as-Judge 连接配置 CRUD。

api_key 只写不读——读取类接口只回 has_api_key 掩码，发起评测时由服务端读取注入运行期。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..constants import LIST_LIMIT_DEFAULT, LIST_LIMIT_MAX
from ..db import get_session
from ..models_db import FeishuUser, JudgeModelConfig
from ..schemas import (
    DefaultJudgePromptOut,
    JudgeModelCreate,
    JudgeModelOut,
    JudgeModelUpdate,
    OptimizeJudgePromptIn,
    OptimizeJudgePromptOut,
)
from ..services import judge_models as jm_svc
from ..services.judge_prompt_optimize import optimize_judge_prompt

router = APIRouter(prefix="/api/judge-models", tags=["judge-models"])


@router.get("", response_model=list[JudgeModelOut])
def list_judge_models(
    limit: int = Query(
        LIST_LIMIT_DEFAULT, ge=1, le=LIST_LIMIT_MAX, description="分页大小"
    ),
    offset: int = Query(0, ge=0, description="分页偏移"),
    session: Session = Depends(get_session),
) -> list[JudgeModelConfig]:
    rows = jm_svc.list_judge_models(session)
    return rows[offset : offset + limit]


@router.get("/default-prompt", response_model=DefaultJudgePromptOut)
def default_judge_prompt() -> DefaultJudgePromptOut:
    from medeval.judges.prompt_template import DEFAULT_PROMPT_TEMPLATE

    return DefaultJudgePromptOut(prompt_template=DEFAULT_PROMPT_TEMPLATE)


@router.post("", response_model=JudgeModelOut, status_code=201)
def create_judge_model(
    payload: JudgeModelCreate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> JudgeModelConfig:
    return jm_svc.create_judge_model(
        session, payload, created_by=current_user.name if current_user else None
    )


@router.post("/optimize-prompt", response_model=OptimizeJudgePromptOut)
async def optimize_judge_prompt_route(payload: OptimizeJudgePromptIn) -> OptimizeJudgePromptOut:
    optimized = await optimize_judge_prompt(payload.prompt)
    return OptimizeJudgePromptOut(optimized_prompt=optimized)


@router.patch("/{model_id}", response_model=JudgeModelOut)
def update_judge_model(
    model_id: int,
    payload: JudgeModelUpdate,
    session: Session = Depends(get_session),
) -> JudgeModelConfig:
    return jm_svc.update_judge_model(session, model_id, payload)


@router.delete("/{model_id}", status_code=204)
def delete_judge_model(model_id: int, session: Session = Depends(get_session)) -> None:
    jm_svc.delete_judge_model(session, model_id)
