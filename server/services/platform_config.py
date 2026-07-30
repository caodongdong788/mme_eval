"""平台的八维评测配置读取服务。"""

from __future__ import annotations

from typing import Any

from medeval.config import load_config
from medeval.evaluation import (
    DIMENSION_DESCRIPTIONS,
    DIMENSION_LABELS,
    DIMENSION_ROLES,
    DIMENSION_STANDARDS,
    GRADE_THRESHOLDS,
    GUIDELINE_RULE,
    GUIDELINE_RULE_DESCRIPTION,
    ROLE_DIMENSIONS,
    ROLE_LABELS,
    ROLE_MAX_SCORES,
    SCORE_ANCHORS,
    TOTAL_MAX_SCORE,
    EvaluationDimension,
)
from medeval.judge_labels import judge_verdict_label_map
from medeval.models import FailureTag

from ..settings import get_settings


# cx-agent SIT 专用账号池。账号由 cx-agent 的 evaluation test account service
# 领取、清空、释放；这里仅作为 MME 的只读参数展示，便于发起评测前确认容量与用途。
_EVALUATION_ACCOUNTS = (
    {
        "pool": "stateless",
        "pool_label": "普通评测",
        "phone": "+8610000000101",
        "verification_code": "731904",
        "user_id": "00000000-0000-0000-0000-000000000101",
        "usage": "无 initial_state 的普通 Case",
    },
    {
        "pool": "stateless",
        "pool_label": "普通评测",
        "phone": "+8610000000104",
        "verification_code": "864173",
        "user_id": "00000000-0000-0000-0000-000000000104",
        "usage": "无 initial_state 的普通 Case",
    },
    {
        "pool": "stateless",
        "pool_label": "普通评测",
        "phone": "+8610000000105",
        "verification_code": "316508",
        "user_id": "00000000-0000-0000-0000-000000000105",
        "usage": "无 initial_state 的普通 Case",
    },
    {
        "pool": "stateless",
        "pool_label": "普通评测",
        "phone": "+8610000000106",
        "verification_code": "759284",
        "user_id": "00000000-0000-0000-0000-000000000106",
        "usage": "无 initial_state 的普通 Case",
    },
    {
        "pool": "stateless",
        "pool_label": "普通评测",
        "phone": "+8610000000107",
        "verification_code": "482691",
        "user_id": "00000000-0000-0000-0000-000000000107",
        "usage": "无 initial_state 的普通 Case",
    },
    {
        "pool": "stateless",
        "pool_label": "普通评测",
        "phone": "+8610000000108",
        "verification_code": "935167",
        "user_id": "00000000-0000-0000-0000-000000000108",
        "usage": "无 initial_state 的普通 Case",
    },
    {
        "pool": "stateless",
        "pool_label": "普通评测",
        "phone": "+8610000000102",
        "verification_code": "846215",
        "user_id": "00000000-0000-0000-0000-000000000102",
        "usage": "无 initial_state 的普通 Case",
    },
    {
        "pool": "stateless",
        "pool_label": "普通评测",
        "phone": "+8610000000103",
        "verification_code": "592638",
        "user_id": "00000000-0000-0000-0000-000000000103",
        "usage": "无 initial_state 的普通 Case",
    },
    {
        "pool": "stateful",
        "pool_label": "长期记忆评测",
        "phone": "+8610000000201",
        "verification_code": "418572",
        "user_id": "00000000-0000-0000-0000-000000000201",
        "usage": "带 initial_state 的用户画像、长期记忆或 Timeline Case",
    },
    {
        "pool": "stateful",
        "pool_label": "长期记忆评测",
        "phone": "+8610000000202",
        "verification_code": "694831",
        "user_id": "00000000-0000-0000-0000-000000000202",
        "usage": "带 initial_state 的用户画像、长期记忆或 Timeline Case",
    },
    {
        "pool": "stateful",
        "pool_label": "长期记忆评测",
        "phone": "+8610000000203",
        "verification_code": "257946",
        "user_id": "00000000-0000-0000-0000-000000000203",
        "usage": "带 initial_state 的用户画像、长期记忆或 Timeline Case",
    },
    {
        "pool": "stateful",
        "pool_label": "长期记忆评测",
        "phone": "+8610000000204",
        "verification_code": "572804",
        "user_id": "00000000-0000-0000-0000-000000000204",
        "usage": "带 initial_state 的用户画像、长期记忆或 Timeline Case",
    },
    {
        "pool": "stateful",
        "pool_label": "长期记忆评测",
        "phone": "+8610000000205",
        "verification_code": "183659",
        "user_id": "00000000-0000-0000-0000-000000000205",
        "usage": "带 initial_state 的用户画像、长期记忆或 Timeline Case",
    },
    {
        "pool": "stateful",
        "pool_label": "长期记忆评测",
        "phone": "+8610000000206",
        "verification_code": "628417",
        "user_id": "00000000-0000-0000-0000-000000000206",
        "usage": "带 initial_state 的用户画像、长期记忆或 Timeline Case",
    },
    {
        "pool": "stateful",
        "pool_label": "长期记忆评测",
        "phone": "+8610000000207",
        "verification_code": "749305",
        "user_id": "00000000-0000-0000-0000-000000000207",
        "usage": "带 initial_state 的用户画像、长期记忆或 Timeline Case",
    },
    {
        "pool": "stateful",
        "pool_label": "长期记忆评测",
        "phone": "+8610000000208",
        "verification_code": "264918",
        "user_id": "00000000-0000-0000-0000-000000000208",
        "usage": "带 initial_state 的用户画像、长期记忆或 Timeline Case",
    },
)


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


def evaluation_accounts() -> dict[str, Any]:
    """返回 MME 使用的 cx-agent 专用评测账号池（仅供已登录的参数页展示）。"""
    return {
        "accounts": list(_EVALUATION_ACCOUNTS),
        "allocation_rule": (
            "每个 Case/run 临时租用一个账号；带非空 initial_state 的 Case 使用长期记忆账号池，"
            "其他 Case 使用普通账号池。Case 完成后自动释放。"
        ),
    }


def evaluation_standard() -> dict[str, Any]:
    return {
        "roles": [
            {
                "key": role,
                "label": ROLE_LABELS[role],
                "max_score": ROLE_MAX_SCORES[role],
                "raw_max_score": len(ROLE_DIMENSIONS[role]) * 5,
                "dimension_count": len(ROLE_DIMENSIONS[role]),
                "normalized": len(ROLE_DIMENSIONS[role]) * 5 != ROLE_MAX_SCORES[role],
            }
            for role in ROLE_LABELS
        ],
        "dimensions": [
            {
                "key": dimension.value,
                "label": DIMENSION_LABELS[dimension],
                "role": DIMENSION_ROLES[dimension],
                "description": DIMENSION_DESCRIPTIONS[dimension],
                "zero_score_description": DIMENSION_STANDARDS[dimension]["zero_score"],
                "full_score_description": DIMENSION_STANDARDS[dimension]["full_score"],
                "max_score": 5,
                "binary": dimension == EvaluationDimension.medical_safety,
                "score_range": (
                    "0 / 5（二值）"
                    if dimension == EvaluationDimension.medical_safety
                    else "0～5（整数）"
                ),
            }
            for dimension in EvaluationDimension
        ],
        "score_anchors": [
            {"score": score, "description": description}
            for score, description in SCORE_ANCHORS.items()
        ],
        "end_max_scores": dict(ROLE_MAX_SCORES),
        "total_max_score": TOTAL_MAX_SCORE,
        "grades": [dict(threshold) for threshold in GRADE_THRESHOLDS],
        "medical_safety_zeroes_total": True,
        "guideline_rule": GUIDELINE_RULE,
        "guideline_rule_description": GUIDELINE_RULE_DESCRIPTION,
    }
