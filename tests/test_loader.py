"""loader 行为回归。"""

from pathlib import Path

import pytest

from medeval.loader import load_cases
from medeval.models import ScoreProfile, Source


def test_load_cases_sets_case_file(tmp_path: Path) -> None:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "foo.yaml").write_text(
        """
sample_id: t1
scenario: s
level: L1
turns:
  - role: user
    content: hi
""".strip(),
        encoding="utf-8",
    )
    cases = load_cases(include=["cases"], base_dir=tmp_path)
    assert len(cases) == 1
    assert cases[0].case_file == "foo.yaml"


def test_legacy_case_version_key_is_ignored(tmp_path: Path) -> None:
    """历史 YAML 残留的 case_version key 应被静默忽略，且 TestCase 不再暴露该属性。"""
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "legacy.yaml").write_text(
        """
sample_id: t1
scenario: s
level: L1
case_version: v1
turns:
  - role: user
    content: hi
""".strip(),
        encoding="utf-8",
    )
    cases = load_cases(include=["cases"], base_dir=tmp_path)
    assert len(cases) == 1
    assert not hasattr(cases[0], "case_version")


def test_legacy_population_difficulty_keys_are_ignored(tmp_path: Path) -> None:
    """历史 YAML 残留的 population / difficulty 应被静默忽略。"""
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "legacy.yaml").write_text(
        """
sample_id: t1
scenario: s
level: L1
population: adult
difficulty: hard
turns:
  - role: user
    content: hi
""".strip(),
        encoding="utf-8",
    )
    cases = load_cases(include=["cases"], base_dir=tmp_path)
    assert len(cases) == 1
    assert not hasattr(cases[0], "population")
    assert not hasattr(cases[0], "difficulty")


def test_source_offline_and_default(tmp_path: Path) -> None:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "offline.yaml").write_text(
        """
sample_id: t1
scenario: s
level: L1
source: offline
turns:
  - role: user
    content: hi
""".strip(),
        encoding="utf-8",
    )
    (case_dir / "default.yaml").write_text(
        """
sample_id: t2
scenario: s
level: L1
turns:
  - role: user
    content: hi
""".strip(),
        encoding="utf-8",
    )
    cases = {c.sample_id: c for c in load_cases(include=["cases"], base_dir=tmp_path)}
    assert cases["t1"].source == Source.offline
    assert cases["t2"].source == Source.offline


def test_legacy_source_expert_crafted_rejected(tmp_path: Path) -> None:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "legacy.yaml").write_text(
        """
sample_id: t1
scenario: s
level: L1
source: expert_crafted
turns:
  - role: user
    content: hi
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_cases(include=["cases"], base_dir=tmp_path)


def test_score_profile_and_filter(tmp_path: Path) -> None:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "cases.yaml").write_text(
        """
- sample_id: k1
  scenario: s
  level: L2
  score_profile: knowledge
  turns:
    - role: user
      content: hi
- sample_id: a1
  scenario: s
  level: L4
  score_profile: adversarial
  turns:
    - role: user
      content: hi
""".strip(),
        encoding="utf-8",
    )
    all_cases = load_cases(include=["cases"], base_dir=tmp_path)
    assert {c.sample_id for c in all_cases} == {"k1", "a1"}
    filtered = load_cases(
        include=["cases"], base_dir=tmp_path, score_profiles=["adversarial"]
    )
    assert len(filtered) == 1
    assert filtered[0].sample_id == "a1"
    assert filtered[0].score_profile == ScoreProfile.adversarial


def test_score_profile_list_coerces_first(tmp_path: Path) -> None:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "multi.yaml").write_text(
        """
sample_id: t1
scenario: s
level: L2
score_profile: [rehab, knowledge]
turns:
  - role: user
    content: hi
""".strip(),
        encoding="utf-8",
    )
    cases = load_cases(include=["cases"], base_dir=tmp_path)
    assert cases[0].score_profile == ScoreProfile.rehab


def test_legacy_tags_key_rejected(tmp_path: Path) -> None:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "legacy.yaml").write_text(
        """
sample_id: t1
scenario: s
level: L1
tags: [adversarial]
turns:
  - role: user
    content: hi
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_cases(include=["cases"], base_dir=tmp_path)


# ── 文件级 defaults 继承（defaults: + cases:）────────────────────────────


def test_defaults_merge_applies_to_each_case(tmp_path: Path) -> None:
    """defaults 逐条注入；case 未声明的字段从 defaults 继承。"""
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "k.yaml").write_text(
        """
defaults:
  scenario: 症状识别
  level: L2
  score_profile: knowledge
  source: offline
  hard_gates:
    no_prescription: true
    require_disclaimer: true
cases:
- sample_id: k1
  sub_scenario: a
  turns:
    - role: user
      content: hi
- sample_id: k2
  sub_scenario: b
  turns:
    - role: user
      content: hi
""".strip(),
        encoding="utf-8",
    )
    cases = {c.sample_id: c for c in load_cases(include=["cases"], base_dir=tmp_path)}
    assert len(cases) == 2
    for c in cases.values():
        assert c.scenario == "症状识别"
        assert c.score_profile == ScoreProfile.knowledge
        assert c.hard_gates.no_prescription is True
        assert c.hard_gates.require_disclaimer is True


def test_defaults_case_override_wins_and_deep_merges(tmp_path: Path) -> None:
    """case 侧字段覆盖 defaults；dict 深合并、list 整体替换。"""
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "k.yaml").write_text(
        """
defaults:
  scenario: 预防筛查
  level: L1
  score_profile: knowledge
  hard_gates:
    no_prescription: true
    require_disclaimer: true
cases:
- sample_id: c1
  turns:
    - role: user
      content: hi
- sample_id: c2
  scenario: 遗传高危
  level: L2
  hard_gates:
    require_disclaimer: false
  turns:
    - role: user
      content: hi
""".strip(),
        encoding="utf-8",
    )
    cases = {c.sample_id: c for c in load_cases(include=["cases"], base_dir=tmp_path)}
    # c1 全继承
    assert cases["c1"].scenario == "预防筛查"
    assert cases["c1"].level.value == "L1"
    # c2 覆盖 scenario/level，hard_gates 深合并：no_prescription 继承、require_disclaimer 覆盖
    assert cases["c2"].scenario == "遗传高危"
    assert cases["c2"].level.value == "L2"
    assert cases["c2"].hard_gates.no_prescription is True
    assert cases["c2"].hard_gates.require_disclaimer is False


def test_defaults_missing_cases_key_raises(tmp_path: Path) -> None:
    """顶层 mapping 含 defaults 但 cases 不是数组 → 报错。"""
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "bad.yaml").write_text(
        """
defaults:
  level: L1
cases:
  sample_id: t1
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_cases(include=["cases"], base_dir=tmp_path)


def test_array_form_still_supported(tmp_path: Path) -> None:
    """历史数组顶层格式不受 defaults 改造影响。"""
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "arr.yaml").write_text(
        """
- sample_id: a1
  scenario: s
  level: L1
  turns:
    - role: user
      content: hi
""".strip(),
        encoding="utf-8",
    )
    cases = load_cases(include=["cases"], base_dir=tmp_path)
    assert len(cases) == 1
    assert cases[0].sample_id == "a1"
