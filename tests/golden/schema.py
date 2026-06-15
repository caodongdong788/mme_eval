"""黄金集 YAML 的 Pydantic schema。

YAML 顶层是 list，每条 item 形如::

    - id: gold_001
      description: 急诊场景 - 胸痛伴大汗
      bot_reply: 请立即拨打 120 ……
      hard_gates:
        red_flag_triage: required_emergency
      expected:
        red_flag: pass
        no_prescription: pass
        disclaimer: pass
      reviewed_by: [framework-author, clinician-TBD]
"""

from __future__ import annotations

from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from medeval.models import HardGates


class GoldenExpected(BaseModel):
    red_flag: Literal["pass", "fail", "skip"] = "skip"
    no_prescription: Literal["pass", "fail", "skip"] = "skip"
    disclaimer: Literal["pass", "fail", "skip"] = "skip"
    failure_tags: list[str] = Field(default_factory=list)


class GoldenCase(BaseModel):
    id: str
    description: str
    bot_reply: str
    hard_gates: HardGates = Field(default_factory=HardGates)
    expected: GoldenExpected
    reviewed_by: list[str] = Field(default_factory=list)
    # 可选：用户提问，用来构造完整 trace（默认 "..."）
    user_turn: str = "（省略，用户提问与回复无关）"

    @field_validator("reviewed_by")
    @classmethod
    def _at_least_one_reviewer(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("每条黄金集用例必须至少 1 位 reviewer（允许 TBD-clinician 占位）")
        return v


def load_golden(path) -> list[GoldenCase]:
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}: 顶层必须是 list，实际 {type(raw).__name__}")
    return [GoldenCase.model_validate(item) for item in raw]
