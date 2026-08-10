"""启动时确保默认判分模型可在页面中直接选择。

连接参数来自 ``config.yaml``。启动时会将默认模型的运行期密钥同步进同连接的模型
记录，便于配置页和 Open API 准确展示可用状态；读取接口仍绝不返回明文 Key。
"""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.config import load_config

from ..models_db import JudgeModelConfig
from ..settings import Settings


DEFAULT_JUDGE_MODEL_NAME = "百炼 DashScope · kimi-k2.6"


def _is_same_default_connection(row: JudgeModelConfig, judge) -> bool:
    return (
        (row.provider or "").strip() == (judge.provider or "").strip()
        and (row.model or "").strip() == (judge.model or "").strip()
        and (row.base_url or "").rstrip("/") == (judge.base_url or "").rstrip("/")
        and (row.api_version or "").strip() == (judge.api_version or "").strip()
    )


def ensure_default_judge_model(session: Session, settings: Settings) -> None:
    """幂等注册默认项；配置不可读时不影响平台启动。"""
    try:
        judge = load_config(settings.config_path).judges.eight_dimension
    except Exception:  # noqa: BLE001 - 配置错误由实际发起评测时统一提示
        return

    if not judge.model:
        return

    resolved_api_key = str(judge.api_key or "").strip() or os.environ.get(
        judge.api_key_env or "", ""
    ).strip()
    # 生产环境中已有的 kimi-k2.6 往往由早期版本以其他名称创建；只要连接配置
    # 与 config.yaml 默认判分模型一致，也一并同步 Key，避免页面误报“未配 Key”。
    if resolved_api_key:
        for row in session.execute(select(JudgeModelConfig)).scalars():
            if _is_same_default_connection(row, judge):
                row.api_key = resolved_api_key

    existing = session.execute(
        select(JudgeModelConfig).where(JudgeModelConfig.name == DEFAULT_JUDGE_MODEL_NAME)
    ).scalar_one_or_none()
    if existing is not None:
        # 旧的生产配置可能尚未声明该字段；默认模型仍需明确关闭思考。
        if existing.enable_thinking is None:
            existing.enable_thinking = False
        if resolved_api_key:
            existing.api_key = resolved_api_key
        return

    session.add(
        JudgeModelConfig(
            name=DEFAULT_JUDGE_MODEL_NAME,
            provider=judge.provider,
            model=judge.model,
            base_url=judge.base_url or "",
            api_version=judge.api_version or "",
            temperature=judge.temperature,
            enable_thinking=judge.enable_thinking if judge.enable_thinking is not None else False,
            pairwise_concurrency=4,
            # 默认 Key 也落库，配置页/Open API 才能准确标识该模型可用；读取接口
            # 始终只暴露 has_api_key，不返回明文。
            api_key=resolved_api_key or None,
            created_by="system",
        )
    )
