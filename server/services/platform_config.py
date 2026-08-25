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
from medeval.scoring_standards import MODEL_COMPARISON_DIMENSIONS

from ..settings import get_settings


def _evaluation_account(
    pool: str, suffix: int, account_codes: dict[str, str]
) -> dict[str, str]:
    prefix = "1" if pool == "stateless" else "2"
    phone = f"+8610000000{prefix}{suffix:02d}"
    user_id = f"00000000-0000-0000-0000-000000000{prefix}{suffix:02d}"
    is_stateful = pool == "stateful"
    return {
        "pool": pool,
        "pool_label": "长期记忆评测" if is_stateful else "普通评测",
        "phone": phone,
        "verification_code": account_codes.get(phone, ""),
        "user_id": user_id,
        "usage": (
            "带 initial_state 的用户画像、长期记忆或 Timeline Case"
            if is_stateful else "无 initial_state 的普通 Case"
        ),
    }


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
    account_codes = get_settings().evaluation_account_codes
    accounts = [
        _evaluation_account(pool, suffix, account_codes)
        for pool in ("stateless", "stateful")
        for suffix in range(1, 9)
    ]
    return {
        "accounts": accounts,
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
        "model_comparison": {
            "key": "model_comparison",
            "label": "模型对比八维",
            "description": (
                "用于从模型能力视角评估单次 Agent 回答；每个维度按 0～5 分评分，"
                "八维满分 40 分。Pairwise 只用于后续比较多个已完成评测结果。"
            ),
            "values": [{"value": str(score), "label": f"{score} 分"} for score in range(6)],
            "dimensions": [
                {
                    "key": item.key,
                    "label": item.label,
                    "description": item.description,
                    "zero_score_description": item.zero_score_description,
                    "full_score_description": item.full_score_description,
                    "max_score": 5,
                    "score_range": "0～5（整数）",
                    "applicability": item.applicability,
                }
                for item in MODEL_COMPARISON_DIMENSIONS
            ],
            "overall_rule": "八个维度等权，每维满分 5 分，总分满分 40 分；60% 及以上为合格。",
            "ttft_rule": (
                "TTFT、端到端延迟和 Token 由平台直接统计，只做性能观测，"
                "不交给 Judge 打分，也不参与 Pairwise 胜负。"
            ),
            "blind_rule": "Pairwise 可在后续对两个或多个已完成结果进行匿名横向比较；不会改写单次评测的分数。",
        },
    }
