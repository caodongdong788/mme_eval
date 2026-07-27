"""评测 job 共享：load config + overrides + judge/adapter 栈。"""

from __future__ import annotations

from typing import Any

from medeval.adapter import build_adapter as _build_adapter
from medeval.config import Config, load_config
from medeval.service import build_judges

from ..settings import Settings
from .config_overrides import (
    apply_adapter_overrides,
    apply_judge_overrides,
    apply_user_simulator_overrides,
)


def prepare_run_config(
    settings: Settings,
    *,
    run_name: str | None = None,
    repeat: int | None = None,
    judge_ov: dict[str, Any] | None = None,
    adapter_ov: dict[str, Any] | None = None,
    extra_judge_ov: dict[str, Any] | None = None,
) -> Config:
    config = load_config(settings.config_path)
    if run_name:
        config.run.name = run_name
    if repeat:
        config.run.repeat = repeat
    apply_judge_overrides(config, judge_ov)
    mode = (adapter_ov or {}).get("evaluation_mode")
    if mode in {"single_turn", "multi_turn"}:
        config.run.evaluation_mode = mode
    simulator_ov = (adapter_ov or {}).get("user_simulator")
    if isinstance(simulator_ov, dict):
        apply_user_simulator_overrides(config, simulator_ov)
    apply_adapter_overrides(config, adapter_ov)
    if extra_judge_ov:
        apply_judge_overrides(config, extra_judge_ov)
    return config


def build_judge_stack(config: Config):
    return build_judges(
        config.judges,
        trigger_aware=config.run.evaluation_mode == "multi_turn",
    )


def build_eval_adapter(config: Config):
    return _build_adapter(config.adapter.type, config.adapter.model_dump())
