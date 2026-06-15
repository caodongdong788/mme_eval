"""config 路由：暴露 config.yaml 里判官（打分模型）的默认值与候选，供前端下拉。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.config import load_config
from medeval.loader import load_cases
from medeval.models import FailureTag
from medeval.reporter.scoring import profile_release_thresholds

from ..auth import get_current_user_optional
from ..db import get_session
from ..models_db import FeishuUser, ReleaseThresholdConfig
from ..settings import get_settings

router = APIRouter(prefix="/api/config", tags=["config"])

# 评分档（profile）→ 中文标签，仅前端展示用。
_PROFILE_LABELS = {
    "default": "默认（兜底）",
    "red_flag": "红旗分诊",
    "adversarial": "对抗",
    "knowledge": "知识科普",
    "rehab": "康复随访",
}


@router.get("/failure-tags")
def failure_tag_labels() -> dict[str, str]:
    """失败标签枚举值 → 中文短标签（取自 FailureTag.label_zh 单一信任源）。"""
    return {tag.value: tag.label_zh for tag in FailureTag}


@router.get("/judge-defaults")
def judge_defaults() -> dict[str, Any]:
    """返回打分模型默认 provider/model/base_url/api_version 与候选模型列表。

    候选来自 config.yaml 中 judges.llm / judges.scoring_point 配置的模型（去重）。
    config 读取失败时返回安全空默认（前端仍可手动输入）。
    """
    settings = get_settings()
    try:
        cfg = load_config(settings.config_path)
    except Exception:  # noqa: BLE001 —— 配置缺失/非法时不阻塞前端
        return {
            "provider": "openai",
            "model": "",
            "base_url": "",
            "api_version": "",
            "model_options": [],
        }

    llm = cfg.judges.llm
    sp = cfg.judges.scoring_point
    options: list[str] = []
    for m in (llm.model, sp.model):
        if m and m not in options:
            options.append(m)

    return {
        "provider": llm.provider,
        "model": llm.model,
        "base_url": llm.base_url,
        "api_version": llm.api_version,
        "model_options": options,
    }


class ProfileCoverage(BaseModel):
    """该评分档对应的用例 score_profile 映射（用于前端展示覆盖范围）。"""

    is_fallback: bool = False
    score_profile: str = ""
    case_count: int = 0


class ReleaseThresholdItem(BaseModel):
    profile: str
    label: str
    max_total: float
    default_threshold: float
    override: Optional[float] = None
    effective: float
    coverage: ProfileCoverage = ProfileCoverage()


class ReleaseThresholdUpdate(BaseModel):
    """按 profile 设置综合分上线阈值；值为 None 或等于默认 → 删除覆盖（恢复默认）。"""

    overrides: dict[str, Optional[float]]


def _scoring_snapshot() -> dict[str, Any]:
    try:
        return load_config(get_settings().config_path).scoring.model_dump(mode="json")
    except Exception:  # noqa: BLE001 —— 配置缺失/非法时退回空（profile_release_thresholds 给 default）
        return {}


def _score_profile_counts() -> dict[str, int]:
    """当前 config 用例集按 score_profile 计数（供阈值页展示覆盖题数）。"""
    try:
        settings = get_settings()
        cfg = load_config(settings.config_path)
        cases = load_cases(
            include=list(cfg.cases.include),
            exclude=list(cfg.cases.exclude),
            base_dir=settings.project_root,
        )
        counts: dict[str, int] = {}
        for c in cases:
            sp = getattr(c.score_profile, "value", c.score_profile)
            counts[str(sp)] = counts.get(str(sp), 0) + 1
        return counts
    except Exception:  # noqa: BLE001
        return {}


def _profile_coverage(profile: str, counts: dict[str, int]) -> ProfileCoverage:
    """各评分档 → 用例 score_profile 的一一映射展示元数据。"""
    if profile == "default":
        return ProfileCoverage(
            is_fallback=True,
            score_profile="default",
            case_count=counts.get("default", 0),
        )
    return ProfileCoverage(
        score_profile=profile,
        case_count=counts.get(profile, 0),
    )


@router.get("/release-thresholds", response_model=list[ReleaseThresholdItem])
def get_release_thresholds(
    session: Session = Depends(get_session),
) -> list[ReleaseThresholdItem]:
    """各评分档的满分上限、默认上线综合分阈值、当前覆盖与覆盖范围（供前端展示/配置）。"""
    scoring = _scoring_snapshot()
    rows = profile_release_thresholds(scoring)
    counts = _score_profile_counts()
    overrides = {
        r.profile: float(r.composite_threshold)
        for r in session.execute(select(ReleaseThresholdConfig)).scalars().all()
    }
    out: list[ReleaseThresholdItem] = []
    for r in rows:
        prof = r["profile"]
        ov = overrides.get(prof)
        coverage = _profile_coverage(prof, counts)
        out.append(
            ReleaseThresholdItem(
                profile=prof,
                label=_PROFILE_LABELS.get(prof, prof),
                max_total=r["max_total"],
                default_threshold=r["default_threshold"],
                override=ov,
                effective=ov if ov is not None else r["default_threshold"],
                coverage=coverage,
            )
        )
    return out


@router.put("/release-thresholds", response_model=list[ReleaseThresholdItem])
def put_release_thresholds(
    payload: ReleaseThresholdUpdate,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> list[ReleaseThresholdItem]:
    """更新按 profile 的综合分上线阈值覆盖。仅作用于之后发起的新评测。"""
    rows = {r["profile"]: r for r in profile_release_thresholds(_scoring_snapshot())}
    existing = {
        r.profile: r
        for r in session.execute(select(ReleaseThresholdConfig)).scalars().all()
    }
    updater = current_user.name if current_user is not None else None

    for profile, value in payload.overrides.items():
        if profile not in rows:
            raise HTTPException(status_code=422, detail=f"未知评分档：{profile}")
        max_total = rows[profile]["max_total"]
        default_threshold = rows[profile]["default_threshold"]
        # 值缺省 / 等于默认 → 删除覆盖（恢复默认，不留无意义行）。
        if value is None or abs(float(value) - default_threshold) < 1e-9:
            if profile in existing:
                session.delete(existing[profile])
            continue
        if float(value) <= 0 or float(value) > max_total + 1e-9:
            raise HTTPException(
                status_code=422,
                detail=f"评分档「{profile}」阈值须在 (0, {max_total}] 内",
            )
        if profile in existing:
            existing[profile].composite_threshold = float(value)
            existing[profile].updated_by = updater
        else:
            session.add(
                ReleaseThresholdConfig(
                    profile=profile,
                    composite_threshold=float(value),
                    updated_by=updater,
                )
            )
    session.flush()
    return get_release_thresholds(session)
