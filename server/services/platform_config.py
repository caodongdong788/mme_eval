"""平台配置 API：失败标签、Judge 标签、判分默认、上线阈值。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.config import load_config
from medeval.judge_labels import judge_verdict_label_map
from medeval.loader import load_cases
from medeval.models import FailureTag
from medeval.reporter.scoring import profile_release_thresholds

from ..models_db import ReleaseThresholdConfig
from ..schemas import (
    ProfileCoverageOut,
    ReleaseThresholdItemOut,
    ReleaseThresholdUpdateRequest,
)
from ..settings import get_settings

PROFILE_LABELS_ZH = {
    "default": "默认（兜底）",
    "red_flag": "红旗分诊",
    "adversarial": "对抗",
    "knowledge": "知识科普",
    "rehab": "康复随访",
}


def failure_tag_labels() -> dict[str, str]:
    return {tag.value: tag.label_zh for tag in FailureTag}


def judge_verdict_labels() -> dict[str, str]:
    return judge_verdict_label_map()


def judge_defaults() -> dict[str, Any]:
    settings = get_settings()
    try:
        cfg = load_config(settings.config_path)
    except Exception:  # noqa: BLE001
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


def _scoring_snapshot() -> dict[str, Any]:
    try:
        return load_config(get_settings().config_path).scoring.model_dump(mode="json")
    except Exception:  # noqa: BLE001
        return {}


def _score_profile_counts() -> dict[str, int]:
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


def _profile_coverage(profile: str, counts: dict[str, int]) -> ProfileCoverageOut:
    if profile == "default":
        return ProfileCoverageOut(
            is_fallback=True,
            score_profile="default",
            case_count=counts.get("default", 0),
        )
    return ProfileCoverageOut(
        score_profile=profile,
        case_count=counts.get(profile, 0),
    )


def get_release_thresholds(session: Session) -> list[ReleaseThresholdItemOut]:
    scoring = _scoring_snapshot()
    rows = profile_release_thresholds(scoring)
    counts = _score_profile_counts()
    overrides = {
        r.profile: float(r.composite_threshold)
        for r in session.execute(select(ReleaseThresholdConfig)).scalars().all()
    }
    out: list[ReleaseThresholdItemOut] = []
    for r in rows:
        prof = r["profile"]
        ov = overrides.get(prof)
        coverage = _profile_coverage(prof, counts)
        out.append(
            ReleaseThresholdItemOut(
                profile=prof,
                label=PROFILE_LABELS_ZH.get(prof, prof),
                max_total=r["max_total"],
                default_threshold=r["default_threshold"],
                override=ov,
                effective=ov if ov is not None else r["default_threshold"],
                coverage=coverage,
            )
        )
    return out


def put_release_thresholds(
    session: Session,
    payload: ReleaseThresholdUpdateRequest,
    *,
    updated_by: Optional[str],
) -> list[ReleaseThresholdItemOut]:
    rows = {r["profile"]: r for r in profile_release_thresholds(_scoring_snapshot())}
    existing = {
        r.profile: r
        for r in session.execute(select(ReleaseThresholdConfig)).scalars().all()
    }

    for profile, value in payload.overrides.items():
        if profile not in rows:
            raise HTTPException(status_code=422, detail=f"未知评分档：{profile}")
        max_total = rows[profile]["max_total"]
        default_threshold = rows[profile]["default_threshold"]
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
            existing[profile].updated_by = updated_by
        else:
            session.add(
                ReleaseThresholdConfig(
                    profile=profile,
                    composite_threshold=float(value),
                    updated_by=updated_by,
                )
            )
    session.flush()
    return get_release_thresholds(session)
