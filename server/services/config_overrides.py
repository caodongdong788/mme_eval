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
)

ADAPTER_OVERRIDE_KEYS = (
    "model",
    "base_url",
    "system_prompt",
    "api_key_env",
    "api_key",
    "temperature",
)


def apply_judge_overrides(config: Config, judge: dict[str, Any] | None) -> None:
    if not judge:
        return
    for target in (config.judges.llm, config.judges.scoring_point):
        for k in JUDGE_OVERRIDE_KEYS:
            v = judge.get(k)
            if v is not None and hasattr(target, k):
                setattr(target, k, v)


def apply_adapter_overrides(config: Config, adapter: dict[str, Any] | None) -> None:
    if not adapter:
        return
    oc = config.adapter.openai_compat
    if oc is None:
        return
    for k in ADAPTER_OVERRIDE_KEYS:
        v = adapter.get(k)
        if v is not None and hasattr(oc, k):
            setattr(oc, k, v)
