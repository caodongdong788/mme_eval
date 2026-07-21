from __future__ import annotations

import copy
from pathlib import Path

import pytest

from medeval.config import Config, ConfigError, load_config, parse_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def minimal() -> dict:
    return {
        "adapter": {
            "type": "openai_compat",
            "openai_compat": {"base_url": "http://x", "model": "m"},
        }
    }


def test_real_config_uses_only_new_judges() -> None:
    cfg = load_config(REPO_ROOT / "config.yaml")
    assert isinstance(cfg, Config)
    assert cfg.judges.eight_dimension.enabled is True
    assert cfg.judges.guideline.enabled is True
    assert not hasattr(cfg, "scoring")


def test_minimal_config_fills_new_defaults() -> None:
    cfg = parse_config(minimal())
    assert cfg.run.repeat == 1
    assert cfg.judges.eight_dimension.enabled is False
    assert cfg.judges.guideline.enabled is False
    assert cfg.thresholds.medical_safety_pass_rate is None


@pytest.mark.parametrize("legacy_key", ["scoring", "score_profiles", "hard_gates"])
def test_legacy_top_level_config_is_rejected(legacy_key: str) -> None:
    raw = minimal()
    raw[legacy_key] = {}
    with pytest.raises(ConfigError):
        parse_config(raw)


@pytest.mark.parametrize("legacy_judge", ["llm", "rule", "scoring_point", "hard_gates"])
def test_legacy_judge_is_rejected(legacy_judge: str) -> None:
    raw = minimal()
    raw["judges"] = {legacy_judge: {"enabled": False}}
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_nested_judge_typo_rejected() -> None:
    raw = minimal()
    raw["judges"] = {"eight_dimension": {"enabled": True, "temperatur": 0}}
    with pytest.raises(ConfigError) as exc:
        parse_config(raw)
    assert "temperatur" in str(exc.value)


def test_free_form_transport_fields_are_allowed() -> None:
    raw = minimal()
    raw["adapter"]["openai_compat"]["extra_body"] = {"thinking": {"type": "enabled"}}
    raw["judges"] = {
        "guideline": {
            "enabled": True,
            "provider": "azure",
            "base_url": "http://gw",
            "api_version": "2024-02-01",
            "default_headers": {"X-Test": "1"},
        }
    }
    cfg = parse_config(raw)
    assert cfg.adapter.openai_compat.extra_body["thinking"]["type"] == "enabled"
    assert cfg.judges.guideline.default_headers == {"X-Test": "1"}


def test_enabled_azure_requires_endpoint_and_api_version() -> None:
    raw = minimal()
    raw["judges"] = {"eight_dimension": {"enabled": True, "provider": "azure"}}
    with pytest.raises(ConfigError) as exc:
        parse_config(raw)
    assert "base_url" in str(exc.value)


def test_unknown_adapter_is_rejected() -> None:
    with pytest.raises(ConfigError):
        parse_config({"adapter": {"type": "bogus"}})


def test_model_dump_roundtrip() -> None:
    cfg = load_config(REPO_ROOT / "config.yaml")
    assert isinstance(parse_config(copy.deepcopy(cfg.model_dump(mode="json"))), Config)


def test_public_snapshot_removes_runtime_secrets() -> None:
    raw = minimal()
    raw["adapter"] = {
        "type": "cx_agent",
        "cx_agent": {"test_token": "BOT-SECRET"},
    }
    raw["judges"] = {
        "eight_dimension": {"api_key": "JUDGE-SECRET"},
    }
    snapshot = parse_config(raw).public_snapshot()
    assert "test_token" not in snapshot["adapter"]["cx_agent"]
    assert "api_key" not in snapshot["judges"]["eight_dimension"]
    assert snapshot["judges"]["eight_dimension"]["api_key_env"] == "OPENAI_API_KEY"
