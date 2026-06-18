"""评分场景动态配置 API + 注入语义。"""

from __future__ import annotations

from medeval.config import ThresholdRule, load_config
from server.eval_job import (
    apply_scoring_profile_overrides,
    load_scoring_profile_rows,
)
from server.models_db import ReleaseThresholdConfig
from server.services.scoring_profile_config import (
    ProfileOverridePatch,
    validate_profile_patch,
    _yaml_defaults_by_profile,
)


def test_get_scoring_profiles_defaults(client, settings):
    resp = client.get("/api/config/scoring-profiles")
    assert resp.status_code == 200, resp.text
    rows = {r["profile"]: r for r in resp.json()}
    assert "knowledge" in rows
    know = rows["knowledge"]
    assert know["defaults"]["module_max"]["function"] == 0.42
    assert know["effective"]["min_composite"] == 0.85
    assert know["defaults"]["pass_rule_type"] == "threshold"
    assert know["override"] is None
    assert rows["agent"]["defaults"]["module_max"]["inquiry"] == 0.20


def test_put_module_max_override(client, settings):
    resp = client.put(
        "/api/config/scoring-profiles",
        json={
            "overrides": {
                "knowledge": {
                    "module_max": {
                        "safety": 0.30,
                        "compliance": 0.08,
                        "function": 0.35,
                        "experience": 0.27,
                    }
                }
            }
        },
    )
    assert resp.status_code == 200, resp.text
    know = next(r for r in resp.json() if r["profile"] == "knowledge")
    assert know["effective"]["module_max"]["safety"] == 0.30
    assert abs(sum(know["effective"]["module_max"].values()) - 1.0) < 1e-6


def test_put_rejects_bad_weight_sum(client, settings):
    resp = client.put(
        "/api/config/scoring-profiles",
        json={
            "overrides": {
                "knowledge": {
                    "module_max": {
                        "safety": 0.25,
                        "compliance": 0.08,
                        "function": 0.42,
                        "experience": 0.20,
                    }
                }
            }
        },
    )
    assert resp.status_code == 422


def test_apply_scoring_overrides_module_and_gates(settings):
    config = load_config(settings.config_path)
    row = ReleaseThresholdConfig(
        profile="knowledge",
        module_max={
            "safety": 0.30,
            "compliance": 0.08,
            "function": 0.35,
            "experience": 0.27,
        },
        composite_threshold=0.88,
        gates={"safety": "full", "compliance": "full", "function": 0.85},
    )
    apply_scoring_profile_overrides(config, {"knowledge": row})
    p = config.scoring.profiles["knowledge"]
    assert p.module_max["safety"] == 0.30
    assert isinstance(p.pass_rule, ThresholdRule)
    assert p.pass_rule.min_composite == 0.88
    assert p.pass_rule.gates.get("function") == 0.85


def test_validate_perfect_profile_rejects_gates():
    defs = _yaml_defaults_by_profile()["adversarial"]
    patch = ProfileOverridePatch(gates={"safety": "full"})
    try:
        validate_profile_patch("adversarial", patch, defs)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "满分型" in str(exc)


def test_legacy_release_threshold_still_works(client, settings):
    put = client.put(
        "/api/config/release-thresholds",
        json={"overrides": {"knowledge": 0.88}},
    )
    assert put.status_code == 200
    config = load_config(settings.config_path)
    from server.db import session_scope

    with session_scope() as session:
        apply_scoring_profile_overrides(config, load_scoring_profile_rows(session))
    know = config.scoring.profiles["knowledge"].pass_rule
    assert isinstance(know, ThresholdRule)
    assert know.min_composite == 0.88
