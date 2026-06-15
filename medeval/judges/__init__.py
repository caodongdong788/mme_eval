"""Judges 包：判分模块。

判分流程：
  1. HardGate（硬门槛）—— 任一 fail 整题 fail，且不再叠加软分
  2. Rule（必含/禁含）—— 进一步明确"业务规则"通过与否
  3. LLM-as-Judge —— 可选，对软指标（共情、问诊完整性等）打分

设计为可独立调用，便于测试和组合。
"""

from .base import BaseJudge
from .hard_gate import HardGateJudge
from .rule import RuleJudge
from .llm import LLMJudge
from .scoring_point import ScoringPointJudge, compute_guideline_match_rate
from .semantic_adjudicator import SemanticRuleAdjudicator
from .aggregator import judge_all, recompute_result_summary

__all__ = [
    "BaseJudge",
    "HardGateJudge",
    "RuleJudge",
    "LLMJudge",
    "ScoringPointJudge",
    "compute_guideline_match_rate",
    "SemanticRuleAdjudicator",
    "judge_all",
    "recompute_result_summary",
]
