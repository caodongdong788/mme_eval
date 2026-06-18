"""评测 job 共享：load config + overrides + judge/adapter 栈。"""

from __future__ import annotations

from typing import Any

from medeval.adapter import build_adapter as _build_adapter
from medeval.config import Config, load_config
from medeval.service import build_adjudicator, build_judges

from ..db import session_scope
from ..settings import Settings
from .config_overrides import apply_adapter_overrides, apply_judge_overrides
from .scoring_profile_config import (
    apply_scoring_profile_overrides,
    load_scoring_profile_rows,
)


def prepare_run_config(
    settings: Settings,
    *,
    run_name: str | None = None,
    repeat: int | None = None,
    judge_ov: dict[str, Any] | None = None,
    adapter_ov: dict[str, Any] | None = None,
    extra_judge_ov: dict[str, Any] | None = None,
    release_thresholds: bool = False,
) -> Config:
    config = load_config(settings.config_path)
    if run_name:
        config.run.name = run_name
    if repeat:
        config.run.repeat = repeat
    apply_judge_overrides(config, judge_ov)
    apply_adapter_overrides(config, adapter_ov)
    if extra_judge_ov:
        apply_judge_overrides(config, extra_judge_ov)
    if release_thresholds:
        with session_scope() as session:
            apply_scoring_profile_overrides(
                config, load_scoring_profile_rows(session)
            )
    return config


def build_judge_stack(config: Config):
    return build_judges(config.judges), build_adjudicator(config.judges)


def build_eval_adapter(config: Config):
    return _build_adapter(config.adapter.type, config.adapter.model_dump())
