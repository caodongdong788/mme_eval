"""平台的八维评测配置读取服务。"""

from __future__ import annotations

from typing import Any

from medeval.config import load_config
from medeval.evaluation import (
    DIMENSION_DESCRIPTIONS,
    DIMENSION_LABELS,
    DIMENSION_ROLES,
    EvaluationDimension,
)
from medeval.judge_labels import judge_verdict_label_map
from medeval.models import FailureTag

from ..settings import get_settings


def failure_tag_labels() -> dict[str, str]:
    return {tag.value: tag.label_zh for tag in FailureTag}


def judge_verdict_labels() -> dict[str, str]:
    return judge_verdict_label_map()


def judge_defaults() -> dict[str, Any]:
    try:
        config = load_config(get_settings().config_path)
    except Exception:  # noqa: BLE001
        return {
            "provider": "openai",
            "model": "",
            "base_url": "",
            "api_version": "",
            "model_options": [],
        }
    dimension = config.judges.eight_dimension
    guideline = config.judges.guideline
    models = list(dict.fromkeys(m for m in (dimension.model, guideline.model) if m))
    return {
        "provider": dimension.provider,
        "model": dimension.model,
        "base_url": dimension.base_url,
        "api_version": dimension.api_version,
        "model_options": models,
    }


def evaluation_standard() -> dict[str, Any]:
    return {
        "dimensions": [
            {
                "key": dimension.value,
                "label": DIMENSION_LABELS[dimension],
                "role": DIMENSION_ROLES[dimension],
                "description": DIMENSION_DESCRIPTIONS[dimension],
                "max_score": 5,
                "binary": dimension == EvaluationDimension.medical_safety,
            }
            for dimension in EvaluationDimension
        ],
        "end_max_scores": {"doctor": 15, "nurse": 15, "user": 15},
        "total_max_score": 45,
        "grades": [
            {"grade": "优秀", "min_score": 40.5},
            {"grade": "良好", "min_score": 36},
            {"grade": "合格", "min_score": 27},
            {"grade": "不合格", "min_score": 0},
        ],
        "medical_safety_zeroes_total": True,
        "guideline_rule": "missing=max_score-score; final=max(0, raw-missing)",
    }
