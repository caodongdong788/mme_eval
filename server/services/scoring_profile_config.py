"""评分场景（score_profile）动态配置：DB 覆盖 → config.scoring 合并。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.config import Config, ThresholdRule, load_config
from medeval.reporter.scoring import (
    PASS_PERFECT,
    PASS_THRESHOLD,
    profile_scoring_config_rows,
)

from ..models_db import ReleaseThresholdConfig
from ..settings import get_settings

_WEIGHT_EPS = 1e-4
_AGENT_PROFILE = "agent"
_STANDARD_MODULES = ("safety", "compliance", "function", "experience")


@dataclass
class ProfileOverridePatch:
    module_max: Optional[dict[str, float]] = None
    function_deduction: Optional[float] = None
    safety_function_deduction: Optional[float] = None
    min_composite: Optional[float] = None
    gates: Optional[dict[str, Any]] = None


def _expected_module_keys(profile: str) -> tuple[str, ...]:
    if profile == _AGENT_PROFILE:
        return (*_STANDARD_MODULES, "inquiry")
    return _STANDARD_MODULES


def _validate_gates(gates: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for dim, req in gates.items():
        if req in ("full", True):
            out[dim] = "full"
            continue
        try:
            frac = float(req)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"gates.{dim} 须为 full 或 (0, 1] 浮点") from exc
        if not 0.0 < frac <= 1.0:
            raise ValueError(f"gates.{dim} 须在 (0, 1] 内")
        out[dim] = frac
    ThresholdRule(min_composite=0.5, gates=out)  # 复用 schema 校验
    return out


def validate_profile_patch(
    profile: str,
    patch: ProfileOverridePatch,
    defaults: dict[str, Any],
) -> ProfileOverridePatch:
    """校验并规范化单 profile 覆盖；不合规抛 ValueError。"""
    pr_type = defaults["pass_rule_type"]
    max_total = float(defaults["max_total"])
    eff_mm = defaults["module_max"]

    if patch.module_max is not None:
        keys = _expected_module_keys(profile)
        if set(patch.module_max.keys()) != set(keys):
            raise ValueError(f"module_max 须包含且仅包含：{', '.join(keys)}")
        for k, v in patch.module_max.items():
            if not 0.0 < float(v) <= 1.0:
                raise ValueError(f"module_max.{k} 须在 (0, 1] 内")
        total = sum(float(v) for v in patch.module_max.values())
        if abs(total - 1.0) > _WEIGHT_EPS:
            raise ValueError(f"module_max 之和须为 1.0，当前 {total:.4f}")
        eff_mm = {k: float(v) for k, v in patch.module_max.items()}

    if patch.function_deduction is not None:
        fn_max = float(eff_mm["function"])
        fd = float(patch.function_deduction)
        if not 0.0 < fd <= fn_max + _WEIGHT_EPS:
            raise ValueError(f"function_deduction 须在 (0, {fn_max}] 内")

    if patch.safety_function_deduction is not None:
        sfd = float(patch.safety_function_deduction)
        if sfd <= 0:
            raise ValueError("safety_function_deduction 须 > 0")

    if patch.min_composite is not None:
        mc = float(patch.min_composite)
        if mc <= 0 or mc > max_total + _WEIGHT_EPS:
            raise ValueError(f"min_composite 须在 (0, {max_total}] 内")

    if patch.gates is not None:
        if pr_type == PASS_PERFECT:
            raise ValueError("满分型场景不可配置维度门槛")
        allowed = set(eff_mm.keys())
        extra = set(patch.gates.keys()) - allowed
        if extra:
            raise ValueError(f"gates 含未知模块：{', '.join(sorted(extra))}")
        patch.gates = _validate_gates(dict(patch.gates))

    return patch


def _yaml_defaults_by_profile() -> dict[str, dict[str, Any]]:
    settings = get_settings()
    cfg = load_config(settings.config_path)
    return {r["profile"]: r for r in profile_scoring_config_rows(cfg.scoring.model_dump(mode="json"))}


def load_scoring_profile_rows(session: Session) -> dict[str, ReleaseThresholdConfig]:
    return {
        r.profile: r
        for r in session.execute(select(ReleaseThresholdConfig)).scalars().all()
    }


def _effective_values(
    defaults: dict[str, Any], row: Optional[ReleaseThresholdConfig]
) -> dict[str, Any]:
    eff_mm = dict(defaults["module_max"])
    if row and row.module_max:
        eff_mm = {k: float(v) for k, v in row.module_max.items()}
    eff_fd = float(defaults["function_deduction"])
    if row and row.function_deduction is not None:
        eff_fd = float(row.function_deduction)
    eff_sfd = float(defaults["safety_function_deduction"])
    if row and row.safety_function_deduction is not None:
        eff_sfd = float(row.safety_function_deduction)
    eff_min = float(defaults["default_min_composite"])
    if row and row.composite_threshold is not None:
        eff_min = float(row.composite_threshold)
    eff_gates = dict(defaults["default_gates"])
    if row and row.gates is not None:
        eff_gates = dict(row.gates)
    max_total = round(sum(eff_mm.values()), 4)
    return {
        "module_max": eff_mm,
        "function_deduction": eff_fd,
        "safety_function_deduction": eff_sfd,
        "min_composite": eff_min,
        "gates": eff_gates,
        "max_total": max_total,
        "pass_rule_type": defaults["pass_rule_type"],
    }


def _defaults_snapshot(defaults: dict[str, Any]) -> dict[str, Any]:
    return _effective_values(defaults, None)


def _override_snapshot(
    defaults: dict[str, Any], row: ReleaseThresholdConfig
) -> Optional[dict[str, Any]]:
    parts: dict[str, Any] = {}
    if row.module_max is not None:
        parts["module_max"] = {k: float(v) for k, v in row.module_max.items()}
    if row.function_deduction is not None:
        parts["function_deduction"] = float(row.function_deduction)
    if row.safety_function_deduction is not None:
        parts["safety_function_deduction"] = float(row.safety_function_deduction)
    if row.composite_threshold is not None:
        parts["min_composite"] = float(row.composite_threshold)
    if row.gates is not None:
        parts["gates"] = dict(row.gates)
    return parts or None


def _is_row_empty_for_defaults(
    defaults: dict[str, Any], row: ReleaseThresholdConfig
) -> bool:
    ov = _override_snapshot(defaults, row)
    if ov is None:
        return True
    defs = _defaults_snapshot(defaults)
    for key in ("module_max", "function_deduction", "safety_function_deduction", "gates"):
        if key in ov:
            if ov[key] != defs.get(key):
                return False
    if "min_composite" in ov:
        if abs(float(ov["min_composite"]) - float(defs["min_composite"])) > _WEIGHT_EPS:
            return False
    return True


def _apply_pass_rule(
    config: Config,
    profile: str,
    eff: dict[str, Any],
    defaults: dict[str, Any],
) -> None:
    del defaults  # ponytail: 调用方已合并 effective
    rule = ThresholdRule(
        min_composite=float(eff["min_composite"]),
        gates=dict(eff["gates"]),
    )
    if profile == "default":
        config.scoring.pass_rule = rule
    elif profile in config.scoring.profiles:
        config.scoring.profiles[profile].pass_rule = rule


def apply_scoring_profile_overrides(
    config: Config, rows: dict[str, ReleaseThresholdConfig] | None
) -> None:
    if not rows:
        return
    yaml_defs = _yaml_defaults_by_profile()
    for profile, row in rows.items():
        if profile not in yaml_defs:
            continue
        defaults = yaml_defs[profile]
        eff = _effective_values(defaults, row)

        if profile == "default":
            config.scoring.module_max = dict(eff["module_max"])
            if row.function_deduction is not None:
                config.scoring.function_deduction = eff["function_deduction"]
            if row.safety_function_deduction is not None:
                config.scoring.safety_function_deduction = eff["safety_function_deduction"]
        elif profile in config.scoring.profiles:
            p = config.scoring.profiles[profile]
            if row.module_max is not None:
                p.module_max = dict(eff["module_max"])
            if row.function_deduction is not None:
                p.function_deduction = eff["function_deduction"]
            if row.safety_function_deduction is not None:
                p.safety_function_deduction = eff["safety_function_deduction"]

        if (
            row.composite_threshold is not None
            or row.gates is not None
        ):
            _apply_pass_rule(config, profile, eff, defaults)


def load_release_threshold_overrides(session) -> dict[str, float]:
    """兼容旧 API：仅返回 min_composite 覆盖。"""
    rows = load_scoring_profile_rows(session)
    out: dict[str, float] = {}
    for profile, row in rows.items():
        if row.composite_threshold is not None:
            out[profile] = float(row.composite_threshold)
    return out


def build_scoring_profile_items(
    session: Session,
    *,
    profile_labels: dict[str, str],
    coverage_fn,
) -> list[dict[str, Any]]:
    yaml_defs = _yaml_defaults_by_profile()
    db_rows = load_scoring_profile_rows(session)
    out: list[dict[str, Any]] = []
    for profile, defaults in yaml_defs.items():
        row = db_rows.get(profile)
        defs_snap = _defaults_snapshot(defaults)
        eff = _effective_values(defaults, row)
        out.append(
            {
                "profile": profile,
                "label": profile_labels.get(profile, profile),
                "coverage": coverage_fn(profile),
                "defaults": defs_snap,
                "override": _override_snapshot(defaults, row) if row else None,
                "effective": eff,
            }
        )
    return out


def put_scoring_profile_overrides(
    session: Session,
    overrides: dict[str, Optional[dict[str, Any]]],
    *,
    updated_by: Optional[str],
) -> None:
    yaml_defs = _yaml_defaults_by_profile()
    existing = load_scoring_profile_rows(session)

    for profile, payload in overrides.items():
        if profile not in yaml_defs:
            raise HTTPException(status_code=422, detail=f"未知评分档：{profile}")
        defaults = yaml_defs[profile]

        if payload is None:
            if profile in existing:
                session.delete(existing[profile])
            continue

        patch = ProfileOverridePatch(
            module_max=payload.get("module_max"),
            function_deduction=payload.get("function_deduction"),
            safety_function_deduction=payload.get("safety_function_deduction"),
            min_composite=payload.get("min_composite"),
            gates=payload.get("gates"),
        )
        try:
            validate_profile_patch(profile, patch, defaults)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        row = existing.get(profile)
        if row is None:
            row = ReleaseThresholdConfig(profile=profile)
            session.add(row)
            existing[profile] = row

        if patch.module_max is not None:
            defs_mm = defaults["module_max"]
            if all(
                abs(float(patch.module_max[k]) - float(defs_mm[k])) < _WEIGHT_EPS
                for k in patch.module_max
            ):
                row.module_max = None
            else:
                row.module_max = patch.module_max
        if patch.function_deduction is not None:
            if abs(float(patch.function_deduction) - float(defaults["function_deduction"])) < _WEIGHT_EPS:
                row.function_deduction = None
            else:
                row.function_deduction = float(patch.function_deduction)
        if patch.safety_function_deduction is not None:
            if abs(
                float(patch.safety_function_deduction)
                - float(defaults["safety_function_deduction"])
            ) < _WEIGHT_EPS:
                row.safety_function_deduction = None
            else:
                row.safety_function_deduction = float(patch.safety_function_deduction)
        if patch.min_composite is not None:
            if abs(float(patch.min_composite) - float(defaults["default_min_composite"])) < _WEIGHT_EPS:
                row.composite_threshold = None
            else:
                row.composite_threshold = float(patch.min_composite)
        if patch.gates is not None:
            if patch.gates == defaults["default_gates"]:
                row.gates = None
            else:
                row.gates = patch.gates

        if _is_row_empty_for_defaults(defaults, row):
            session.delete(row)
            existing.pop(profile, None)

    session.flush()
