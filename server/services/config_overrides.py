"""将网页/重判参数合并进 typed Config（不改 config.yaml 文件）。"""

from __future__ import annotations

from typing import Any

from medeval.config import Config

JUDGE_OVERRIDE_KEYS = (
    "enabled",
    "provider",
    "model",
    "base_url",
    "api_version",
    "api_key_env",
    "api_key",
    "temperature",
    "enable_thinking",
)

ADAPTER_OVERRIDE_KEYS = (
    "model",
    "base_url",
    "system_prompt",
    "api_key_env",
    "api_key",
    "temperature",
    "enable_rag",
    "enable_system_prompt",
)


def apply_judge_overrides(config: Config, judge: dict[str, Any] | None) -> None:
    if not judge:
        return
    for target in (config.judges.eight_dimension, config.judges.guideline):
        for k in JUDGE_OVERRIDE_KEYS:
            v = judge.get(k)
            if v is not None and hasattr(target, k):
                setattr(target, k, v)


def apply_user_simulator_overrides(
    config: Config, simulator: dict[str, Any] | None
) -> None:
    """仅覆盖动态用户模拟器；与判官复用同一类 LLM 连接配置。"""
    if not simulator:
        return
    for k in JUDGE_OVERRIDE_KEYS:
        v = simulator.get(k)
        if v is not None and hasattr(config.user_simulator, k):
            setattr(config.user_simulator, k, v)


def apply_adapter_overrides(config: Config, adapter: dict[str, Any] | None) -> None:
    if not adapter:
        return
    # cx-agent 的 RAG / 系统提示词开关属于测试路由能力，不应混入 OpenAI 兼容 adapter。
    if config.adapter.type == "cx_agent":
        cx_agent = config.adapter.cx_agent
        if cx_agent is not None and isinstance(adapter.get("enable_rag"), bool):
            cx_agent.enable_rag = adapter["enable_rag"]
        if cx_agent is not None and isinstance(adapter.get("enable_system_prompt"), bool):
            cx_agent.enable_system_prompt = adapter["enable_system_prompt"]
        return

    oc = config.adapter.openai_compat
    if oc is None:
        return
    for k in ADAPTER_OVERRIDE_KEYS:
        v = adapter.get(k)
        if v is not None and hasattr(oc, k):
            setattr(oc, k, v)
