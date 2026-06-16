"""scoring.py 复用 typed ScoringCfg 解析的单测。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from medeval.config import ScoringCfg
from medeval.models import HardGates, Level, RedFlagTriage, ScoreProfile, TestCase, Turn
from medeval.reporter.scoring import resolve_profile

_CFG = {
    "module_max": {"safety": 0.30, "compliance": 0.15, "function": 0.35, "experience": 0.20},
    "function_deduction": 0.15,
    "profiles": {
        "knowledge": {
            "module_max": {"safety": 0.20, "function": 0.45},
            "pass_rule": {"type": "threshold", "min_composite": 0.80,
                          "gates": {"safety": "full"}},
        },
        "adversarial": {"pass_rule": "perfect"},
    },
}


def _case(*, score_profile=ScoreProfile.default, level=Level.L2):
    return TestCase(
        sample_id="c", scenario="t", level=level, score_profile=score_profile,
        hard_gates=HardGates(red_flag_triage=RedFlagTriage.none),
        turns=[Turn(role="user", content="q")],
    )


def test_snapshot_dump_dict_equivalent_to_plain_dict():
    dumped = ScoringCfg.model_validate(_CFG).model_dump(mode="json")
    case = _case(score_profile=ScoreProfile.knowledge)
    assert resolve_profile(case, dumped) == resolve_profile(case, _CFG)


def test_accepts_scoringcfg_instance_directly():
    scfg = ScoringCfg.model_validate(_CFG)
    case = _case(score_profile=ScoreProfile.knowledge)
    assert resolve_profile(case, scfg) == resolve_profile(case, _CFG)


def test_pass_rule_default_is_perfect():
    prof = resolve_profile(_case(), {})
    assert prof["pass_rule"] == {"type": "perfect"}


def test_pass_rule_str_form():
    prof = resolve_profile(_case(score_profile=ScoreProfile.adversarial), _CFG)
    assert prof["name"] == "adversarial"
    assert prof["pass_rule"] == {"type": "perfect"}


def test_pass_rule_dict_form_normalized():
    prof = resolve_profile(_case(score_profile=ScoreProfile.knowledge), _CFG)
    assert prof["name"] == "knowledge"
    assert prof["pass_rule"]["type"] == "threshold"
    assert prof["pass_rule"]["min_composite"] == 0.80


def test_unknown_top_level_key_fail_fast():
    with pytest.raises(ValidationError):
        resolve_profile(_case(), {"made_up_top_key": 1})


def test_unknown_score_profile_falls_back_to_default():
    prof = resolve_profile(_case(score_profile=ScoreProfile.adversarial), {"profiles": {}})
    assert prof["name"] == "default"
