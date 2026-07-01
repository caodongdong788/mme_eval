"""config 类型化校验单测（change 2026-06-02-typed-config-validation）。

覆盖：
  - 现网 config.yaml 合法通过
  - 分区 forbid：结构化节点拼错被拒；自由叶子允许额外键
  - 类型错 / 枚举错 / 跨字段错（azure 缺项、adapter.type 与子块不匹配）被拒
  - 默认值填充
  - pass_rule 三种写法
  - load_config 友好报错（ConfigError 含键路径）
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from medeval.config import Config, ConfigError, load_config, parse_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def _minimal() -> dict:
    """最小合法配置（adapter.type 必填 + 对应子块）。"""
    return {
        "adapter": {
            "type": "openai_compat",
            "openai_compat": {"base_url": "http://x", "model": "m"},
        }
    }


def _minimal_cx_agent() -> dict:
    return {
        "adapter": {
            "type": "cx_agent",
            "cx_agent": {},
        }
    }


# --- 合法路径 --------------------------------------------------------------


def test_real_config_yaml_is_valid():
    cfg = load_config(REPO_ROOT / "config.yaml")
    assert isinstance(cfg, Config)
    assert cfg.adapter.type == "cx_agent"
    assert cfg.adapter.cx_agent.base_url == "http://localhost:3000"
    assert cfg.reporter.lark.enabled is False
    assert cfg.judges.llm.enabled is True
    assert cfg.judges.llm.provider == "openai"
    assert cfg.judges.llm.model == "gpt-5.4-pro"
    assert cfg.judges.llm.api_key_env == "POE_API_KEY"
    assert cfg.scoring.profiles  # 有 profile 配置


def test_minimal_config_fills_defaults():
    cfg = parse_config(_minimal())
    assert cfg.run.repeat == 1
    assert cfg.run.concurrency == 4
    assert cfg.reporter.formats == ["markdown"]
    assert cfg.judges.hard_gates.enabled is True
    assert cfg.judges.rule.normalize is True
    # scoring 数值默认不在此层（归 scoring.py），这里为空容器
    assert cfg.scoring.module_max == {}


def test_cx_agent_config_is_valid():
    cfg = parse_config(_minimal_cx_agent())
    assert cfg.adapter.type == "cx_agent"
    assert cfg.adapter.cx_agent.base_url == "http://localhost:3000"
    assert cfg.adapter.cx_agent.test_token_env == "CX_AGENT_TEST_TOKEN"


# --- forbid 抓拼错 ---------------------------------------------------------


def test_top_level_typo_rejected():
    raw = _minimal()
    raw["adaptor"] = {}  # 误拼 adapter
    with pytest.raises(ConfigError) as ei:
        parse_config(raw)
    assert "adaptor" in str(ei.value)


def test_nested_judge_typo_rejected():
    raw = _minimal()
    raw["judges"] = {"llm": {"enabled": True, "self_consistensy": 3}}  # 拼错
    with pytest.raises(ConfigError) as ei:
        parse_config(raw)
    assert "self_consistensy" in str(ei.value)


def test_scoring_typo_rejected():
    raw = _minimal()
    raw["scoring"] = {"function_deductio": 0.1}  # 拼错
    with pytest.raises(ConfigError):
        parse_config(raw)


# --- 自由叶子放行 ----------------------------------------------------------


def test_free_form_leaves_allow_extra_keys():
    raw = _minimal()
    raw["adapter"]["openai_compat"]["extra_body"] = {"thinking": {"type": "enabled"}}
    raw["judges"] = {
        "llm": {
            "enabled": True,
            "provider": "azure",
            "base_url": "http://gw",
            "api_version": "2024-02-01",
            "default_headers": {"X-Whatever": "1", "X-Another": "2"},
        }
    }
    raw["scoring"] = {"module_max": {"safety": 0.4, "made_up_dim": 0.1}}
    cfg = parse_config(raw)
    assert cfg.adapter.openai_compat.extra_body == {"thinking": {"type": "enabled"}}
    assert cfg.judges.llm.default_headers["X-Another"] == "2"
    assert cfg.scoring.module_max["made_up_dim"] == 0.1


def test_profile_names_free_but_fields_forbidden():
    raw = _minimal()
    raw["scoring"] = {"profiles": {"my_custom_profile": {"function_deduction": 0.2}}}
    cfg = parse_config(raw)
    assert "my_custom_profile" in cfg.scoring.profiles
    # profile 内部字段拼错应被拒
    raw["scoring"] = {"profiles": {"p": {"function_deductio": 0.2}}}
    with pytest.raises(ConfigError):
        parse_config(raw)


# --- 类型 / 枚举错 ---------------------------------------------------------


def test_type_error_rejected():
    raw = _minimal()
    raw["run"] = {"concurrency": "four"}
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_provider_enum_rejected():
    raw = _minimal()
    raw["judges"] = {"llm": {"enabled": True, "provider": "anthropic"}}
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_aggregate_enum_rejected():
    raw = _minimal()
    raw["judges"] = {"llm": {"enabled": True, "aggregate": "mean"}}
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_self_consistency_must_be_ge_1():
    raw = _minimal()
    raw["judges"] = {"scoring_point": {"enabled": True, "self_consistency": 0}}
    with pytest.raises(ConfigError):
        parse_config(raw)


# --- 跨字段错 --------------------------------------------------------------


def test_azure_missing_api_version_rejected():
    raw = _minimal()
    raw["judges"] = {
        "llm": {"enabled": True, "provider": "azure", "base_url": "http://gw"}
    }
    with pytest.raises(ConfigError) as ei:
        parse_config(raw)
    assert "api_version" in str(ei.value)


def test_azure_disabled_not_validated():
    # 未启用的 azure 判官不强校验必填项（与运行期行为一致）
    raw = _minimal()
    raw["judges"] = {"llm": {"enabled": False, "provider": "azure"}}
    cfg = parse_config(raw)
    assert cfg.judges.llm.provider == "azure"


def test_adapter_type_subblock_mismatch_rejected():
    raw = {"adapter": {"type": "http"}}  # 声明 http 却无 http 子块
    with pytest.raises(ConfigError) as ei:
        parse_config(raw)
    assert "http" in str(ei.value)


def test_cx_agent_subblock_required():
    raw = {"adapter": {"type": "cx_agent"}}
    with pytest.raises(ConfigError) as ei:
        parse_config(raw)
    assert "cx_agent" in str(ei.value)


def test_adapter_type_required():
    with pytest.raises(ConfigError):
        parse_config({"run": {"name": "x"}})  # 缺 adapter


def test_adapter_type_unknown_rejected_via_registry():
    # adapter.type 不在注册表中 → 友好报错（列已支持类型），与工厂口径一致
    raw = {"adapter": {"type": "bogus", "openai_compat": {"base_url": "http://x"}}}
    with pytest.raises(ConfigError) as ei:
        parse_config(raw)
    msg = str(ei.value)
    assert "不被支持" in msg
    assert "openai_compat" in msg  # 候选清单


# --- pass_rule 三种写法 ----------------------------------------------------


def test_pass_rule_perfect_string():
    raw = _minimal()
    raw["scoring"] = {"profiles": {"p": {"pass_rule": "perfect"}}}
    cfg = parse_config(raw)
    assert cfg.scoring.profiles["p"].pass_rule == "perfect"


def test_pass_rule_threshold_dict():
    raw = _minimal()
    raw["scoring"] = {
        "profiles": {
            "p": {
                "pass_rule": {
                    "type": "threshold",
                    "min_composite": 0.8,
                    "gates": {"safety": "full"},
                }
            }
        }
    }
    cfg = parse_config(raw)
    pr = cfg.scoring.profiles["p"].pass_rule
    assert pr.min_composite == 0.8
    assert pr.gates == {"safety": "full"}


def test_pass_rule_gate_value_typo_rejected():
    raw = _minimal()
    raw["scoring"] = {
        "profiles": {"p": {"pass_rule": {"min_composite": 0.8, "gates": {"safety": "fulll"}}}}
    }
    with pytest.raises(ConfigError):
        parse_config(raw)


# --- model_dump 等价（config_snapshot 用） ---------------------------------


def test_model_dump_roundtrips_to_dict():
    cfg = load_config(REPO_ROOT / "config.yaml")
    dumped = cfg.model_dump(mode="json")
    assert isinstance(dumped, dict)
    assert dumped["adapter"]["type"] == "cx_agent"
    # 重新校验 dump 结果应仍然合法（幂等）
    assert isinstance(parse_config(copy.deepcopy(dumped)), Config)
