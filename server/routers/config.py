"""config 路由：暴露 config.yaml 里判官（打分模型）的默认值与候选，供前端下拉。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..db import get_session
from ..models_db import FeishuUser
from ..schemas import (
    ProfileCoverageOut,
    ReleaseThresholdItemOut,
    ReleaseThresholdUpdateRequest,
)
from ..services import platform_config as cfg_svc

router = APIRouter(prefix="/api/config", tags=["config"])

# 向后兼容 re-export（历史从此模块导入 schema 名）
ProfileCoverage = ProfileCoverageOut
ReleaseThresholdItem = ReleaseThresholdItemOut
ReleaseThresholdUpdate = ReleaseThresholdUpdateRequest


@router.get("/failure-tags")
def failure_tag_labels() -> dict[str, str]:
    """失败标签枚举值 → 中文短标签（取自 FailureTag.label_zh 单一信任源）。"""
    return cfg_svc.failure_tag_labels()


@router.get("/judge-verdict-labels")
def judge_verdict_labels() -> dict[str, str]:
    """Judge verdict 全名 → 中文展示标签（取自 medeval.judge_labels 单一信任源）。"""
    return cfg_svc.judge_verdict_labels()


@router.get("/judge-defaults")
def judge_defaults() -> dict[str, Any]:
    """返回打分模型默认 provider/model/base_url/api_version 与候选模型列表。"""
    return cfg_svc.judge_defaults()


@router.get("/release-thresholds", response_model=list[ReleaseThresholdItemOut])
def get_release_thresholds(
    session: Session = Depends(get_session),
) -> list[ReleaseThresholdItemOut]:
    return cfg_svc.get_release_thresholds(session)


@router.put("/release-thresholds", response_model=list[ReleaseThresholdItemOut])
def put_release_thresholds(
    payload: ReleaseThresholdUpdateRequest,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> list[ReleaseThresholdItemOut]:
    updater = current_user.name if current_user is not None else None
    return cfg_svc.put_release_thresholds(session, payload, updated_by=updater)
