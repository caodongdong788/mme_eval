"""按场景（profile）配置综合分上线阈值：API CRUD + 注入语义 + 仅新评测。"""

from __future__ import annotations

from medeval.config import ThresholdRule, load_config
from server.eval_job import (
    apply_release_threshold_overrides,
    load_release_threshold_overrides,
)
from server.models_db import ReleaseThresholdConfig


# ── API ─────────────────────────────────────────────────────────────────────


def test_get_release_thresholds_defaults(client, settings):
    resp = client.get("/api/config/release-thresholds")
    assert resp.status_code == 200, resp.text
    rows = {r["profile"]: r for r in resp.json()}
    assert {"default", "adversarial", "knowledge"} <= set(rows)
    # 对抗档（perfect）默认阈值 = 满分上限；知识档（threshold）= 0.80
    assert rows["adversarial"]["default_threshold"] == rows["adversarial"]["max_total"]
    assert abs(rows["knowledge"]["default_threshold"] - 0.80) < 1e-9
    # 未配置时 override 为空、effective = 默认
    assert rows["adversarial"]["override"] is None
    assert rows["adversarial"]["effective"] == rows["adversarial"]["default_threshold"]
    # default 为兜底档
    assert rows["default"]["coverage"]["is_fallback"] is True
    assert rows["default"]["coverage"]["score_profile"] == "default"
    # 非 default 档按 score_profile 一一映射，且内置集有题数
    adv = rows["adversarial"]
    assert adv["coverage"]["score_profile"] == "adversarial"
    assert adv["coverage"]["case_count"] > 0
    know = rows["knowledge"]
    assert know["coverage"]["score_profile"] == "knowledge"
    assert know["coverage"]["case_count"] > 0


def test_put_then_get_override(client, settings):
    put = client.put(
        "/api/config/release-thresholds",
        json={"overrides": {"adversarial": 0.95}},
    )
    assert put.status_code == 200, put.text
    rows = {r["profile"]: r for r in put.json()}
    assert rows["adversarial"]["override"] == 0.95
    assert rows["adversarial"]["effective"] == 0.95
    # 再 GET 持久化生效
    rows2 = {r["profile"]: r for r in client.get("/api/config/release-thresholds").json()}
    assert rows2["adversarial"]["override"] == 0.95


def test_put_rejects_over_max(client, settings):
    resp = client.put(
        "/api/config/release-thresholds",
        json={"overrides": {"adversarial": 1.5}},
    )
    assert resp.status_code == 422


def test_put_rejects_unknown_profile(client, settings):
    resp = client.put(
        "/api/config/release-thresholds",
        json={"overrides": {"nope": 0.5}},
    )
    assert resp.status_code == 422


def test_put_value_equal_default_removes_override(client, settings):
    # 先设一个覆盖
    client.put("/api/config/release-thresholds", json={"overrides": {"knowledge": 0.7}})
    # 再设回默认 0.80 → 删除覆盖
    client.put("/api/config/release-thresholds", json={"overrides": {"knowledge": 0.8}})
    rows = {r["profile"]: r for r in client.get("/api/config/release-thresholds").json()}
    assert rows["knowledge"]["override"] is None


# ── 注入语义 ──────────────────────────────────────────────────────────────────


def test_apply_overrides_changes_pass_rule_and_keeps_gates(settings):
    config = load_config(settings.config_path)
    apply_release_threshold_overrides(config, {"adversarial": 0.95, "knowledge": 0.85})

    adv = config.scoring.profiles["adversarial"].pass_rule
    assert isinstance(adv, ThresholdRule)
    assert adv.min_composite == 0.95
    assert dict(adv.gates) == {}  # 对抗原为 perfect，无 gates

    know = config.scoring.profiles["knowledge"].pass_rule
    assert isinstance(know, ThresholdRule)
    assert know.min_composite == 0.85
    # 知识档原有 safety/compliance 生死线 gates 必须保留
    assert know.gates.get("safety") == "full"
    assert know.gates.get("compliance") == "full"


def test_apply_overrides_empty_is_noop(settings):
    config = load_config(settings.config_path)
    before = config.scoring.profiles["adversarial"].pass_rule
    apply_release_threshold_overrides(config, {})
    assert config.scoring.profiles["adversarial"].pass_rule == before


def test_load_overrides_reads_db(session, settings):
    session.add(ReleaseThresholdConfig(profile="adversarial", composite_threshold=0.95))
    session.commit()
    ov = load_release_threshold_overrides(session)
    assert ov == {"adversarial": 0.95}
