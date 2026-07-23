"""启动时确保默认判分模型可在页面中直接选择。

连接参数来自 ``config.yaml``，密钥始终由该配置的 ``api_key_env`` 在运行期读取，
不会复制到数据库或返回前端。用户随后创建的模型仍可以自行保存 API Key。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.config import load_config

from ..models_db import JudgeModelConfig
from ..settings import Settings


DEFAULT_JUDGE_MODEL_NAME = "百炼 DashScope · kimi-k2.6"


def ensure_default_judge_model(session: Session, settings: Settings) -> None:
    """幂等注册默认项；配置不可读时不影响平台启动。"""
    try:
        judge = load_config(settings.config_path).judges.eight_dimension
    except Exception:  # noqa: BLE001 - 配置错误由实际发起评测时统一提示
        return

    if not judge.model:
        return

    existing = session.execute(
        select(JudgeModelConfig).where(JudgeModelConfig.name == DEFAULT_JUDGE_MODEL_NAME)
    ).scalar_one_or_none()
    if existing is not None:
        return

    session.add(
        JudgeModelConfig(
            name=DEFAULT_JUDGE_MODEL_NAME,
            provider=judge.provider,
            model=judge.model,
            base_url=judge.base_url or "",
            api_version=judge.api_version or "",
            temperature=judge.temperature,
            enable_thinking=judge.enable_thinking,
            pairwise_concurrency=4,
            # 不落库密钥：LLMBackend 会沿用 config 的 api_key_env（LLM_API_KEY）。
            api_key=None,
            created_by="system",
        )
    )
