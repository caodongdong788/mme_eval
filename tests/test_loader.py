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
