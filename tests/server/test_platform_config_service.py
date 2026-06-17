"""failure_tag_labels / judge_defaults 等纯逻辑单测。"""

from __future__ import annotations

from server.services import platform_config as cfg_svc


def test_failure_tag_labels_non_empty():
    labels = cfg_svc.failure_tag_labels()
    assert isinstance(labels, dict)
    assert len(labels) > 0
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in labels.items())


def test_judge_verdict_labels_has_hard_gate():
    labels = cfg_svc.judge_verdict_labels()
    assert "hard_gate.red_flag" in labels
    assert labels["hard_gate.red_flag"]


def test_profile_labels_zh_covers_default():
    assert cfg_svc.PROFILE_LABELS_ZH["default"]


def test_profile_labels_zh_covers_all_scoring_profiles():
    expected = {"default", "red_flag", "adversarial", "knowledge", "rehab", "population", "agent"}
    assert expected <= set(cfg_svc.PROFILE_LABELS_ZH.keys())
