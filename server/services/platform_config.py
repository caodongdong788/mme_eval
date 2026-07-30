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


# cx-agent SIT 专用账号池。账号由 cx-agent 的 evaluation test account service
# 领取、清空、释放；此处仅用于 MME 参数页的只读展示。
_ACCOUNT_CODES = {
    "+8610000000101": "731904", "+8610000000102": "846215",
    "+8610000000103": "592638", "+8610000000104": "864173",
    "+8610000000105": "316508", "+8610000000106": "759284",
    "+8610000000107": "482691", "+8610000000108": "935167",
    "+8610000000201": "418572", "+8610000000202": "694831",
    "+8610000000203": "257946", "+8610000000204": "572804",
    "+8610000000205": "183659", "+8610000000206": "628417",
    "+8610000000207": "749305", "+8610000000208": "264918",
}


def _evaluation_account(pool: str, suffix: int) -> dict[str, str]:
    prefix = "1" if pool == "stateless" else "2"
    phone = f"+8610000000{prefix}{suffix:02d}"
    user_id = f"00000000-0000-0000-0000-000000000{prefix}{suffix:02d}"
    is_stateful = pool == "stateful"
    return {
        "pool": pool,
        "pool_label": "长期记忆评测" if is_stateful else "普通评测",
        "phone": phone,
        "verification_code": _ACCOUNT_CODES[phone],
        "user_id": user_id,
        "usage": (
            "带 initial_state 的用户画像、长期记忆或 Timeline Case"
            if is_stateful else "无 initial_state 的普通 Case"
        ),
    }


_EVALUATION_ACCOUNTS = tuple(
    _evaluation_account(pool, suffix)
    for pool in ("stateless", "stateful")
    for suffix in range(1, 9)
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
    return {
        "accounts": list(_EVALUATION_ACCOUNTS),
        "allocation_rule": (
            "每个 Case/run 临时租用一个账号；带非空 initial_state 的 Case 使用长期记忆账号池，"
            "其他 Case 使用普通账号池。Case 完成后自动释放。"
        ),
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
        "guideline_rule": "untriggered=0; missing=max_score-score; final=max(0, raw-missing)",
    }
