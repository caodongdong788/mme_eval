"""Judge fingerprint 漂移保护测试。

任何关键词表 / prompt / 正则字面量的改动都会改变以下硬编码的 fingerprint，
触发此测试失败，强制人工 review。修改流程：

  1. 评估改动是否真的需要让历史报告不可对比
  2. 若需要，更新本测试里的硬编码值
  3. 在 docs/heuristics-changelog.md 中登记此次变更
     （随 govern-hard-gate-heuristics 提案上线）
"""

from __future__ import annotations

import json

from medeval.judges.base import stable_hash
from medeval.judges.hard_gate import HardGateJudge
from medeval.judges.llm import LLMJudge
from medeval.judges.rule import RuleJudge


# 当前提交点的稳定基线 —— 任何修改都需要更新这里
EXPECTED_FINGERPRINTS: dict[str, str] = {
    "hard_gate": "d7636ecf0b23",
    "rule_normalize_on": "f59e4da96fea",
    "rule_normalize_off": "33cd41e4d711",
    "llm_default": "a8f27bd01bc6",
}


def test_hard_gate_fingerprint_stable():
    fp = HardGateJudge().fingerprint()
    assert fp == EXPECTED_FINGERPRINTS["hard_gate"], (
        f"HardGate fingerprint drifted: {fp}. "
        "请检查关键词表/正则改动是否符合预期，并更新 EXPECTED_FINGERPRINTS。"
    )


def test_rule_fingerprint_depends_on_normalize():
    fp_on = RuleJudge(normalize=True).fingerprint()
    fp_off = RuleJudge(normalize=False).fingerprint()
    assert fp_on == EXPECTED_FINGERPRINTS["rule_normalize_on"]
    assert fp_off == EXPECTED_FINGERPRINTS["rule_normalize_off"]
    assert fp_on != fp_off, "normalize 开关必须改变 fingerprint"


def test_llm_fingerprint_stable():
    fp = LLMJudge().fingerprint()
    assert fp == EXPECTED_FINGERPRINTS["llm_default"]


def test_llm_fingerprint_changes_with_model():
    fp1 = LLMJudge(enabled=False, model="gpt-4o-mini", temperature=0.0).fingerprint()
    fp2 = LLMJudge(enabled=False, model="gpt-4o", temperature=0.0).fingerprint()
    fp3 = LLMJudge(enabled=False, model="gpt-4o-mini", temperature=0.2).fingerprint()
    assert fp1 != fp2, "model 变化必须改变 fingerprint"
    assert fp1 != fp3, "temperature 变化必须改变 fingerprint"


def test_llm_fingerprint_ignores_api_key_env():
    """切换 api_key_env / base_url 不应改变判分逻辑 fingerprint."""
    fp1 = LLMJudge(api_key_env="OPENAI_API_KEY").fingerprint()
    fp2 = LLMJudge(api_key_env="ARK_API_KEY", base_url="https://x.test").fingerprint()
    assert fp1 == fp2


def test_stable_hash_is_deterministic():
    """stable_hash 必须对相同 dict 给出相同结果，与键序无关。"""
    a = {"a": 1, "b": [1, 2, 3]}
    b = {"b": [1, 2, 3], "a": 1}
    assert stable_hash(a) == stable_hash(b)
    # 字符串变化必须导致 hash 变化
    assert stable_hash(a) != stable_hash({"a": 1, "b": [1, 2, 4]})
    # 输出长度恰好 12
    assert len(stable_hash(a)) == 12


def test_stable_hash_handles_unicode():
    """中文不会被 escape，hash 应稳定。"""
    payload = {"prompt": "你是一名严格的医疗 chatbot 评测员。"}
    fp = stable_hash(payload)
    assert len(fp) == 12
    # 多次调用必须一致
    assert stable_hash(payload) == fp
