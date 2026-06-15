"""按 profile 的综合分上线阈值覆盖（DB → config.scoring）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from medeval.config import Config, ThresholdRule

from ..db import session_scope
from ..models_db import ReleaseThresholdConfig


def load_release_threshold_overrides(session) -> dict[str, float]:
    """读取按 profile 的「综合分上线阈值」覆盖（无行=空，表示沿用 config.yaml）。"""
    rows = session.execute(select(ReleaseThresholdConfig)).scalars().all()
    return {r.profile: float(r.composite_threshold) for r in rows}


def apply_release_threshold_overrides(
    config: Config, overrides: dict[str, float] | None
) -> None:
    if not overrides:
        return

    def _gates_of(pr: Any) -> dict[str, Any]:
        if isinstance(pr, ThresholdRule):
            return dict(pr.gates)
        return {}

    scoring = config.scoring
    for profile, thr in overrides.items():
        if profile == "default":
            scoring.pass_rule = ThresholdRule(
                min_composite=float(thr), gates=_gates_of(scoring.pass_rule)
            )
        elif profile in scoring.profiles:
            p = scoring.profiles[profile]
            p.pass_rule = ThresholdRule(
                min_composite=float(thr), gates=_gates_of(p.pass_rule)
            )
