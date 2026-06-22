"""记忆召回专集回归（change add-memory-recall-suite）。"""

from __future__ import annotations

from pathlib import Path

from medeval.loader import load_cases

ROOT = Path(__file__).resolve().parent.parent
SUITE_DIR = "cases/breast_cancer"

MEMORY_MODES = (
    "隐式综合",
    "显式召回",
    "干扰召回",
    "信息更正",
    "抗假记忆",
)


def _memory_cases():
    return [c for c in load_cases(include=[SUITE_DIR], base_dir=ROOT) if c.sample_id.startswith("bc_mem_")]


def test_memory_suite_count_and_scenario():
    cases = _memory_cases()
    assert len(cases) == 15, f"记忆专集应为 15 题，实得 {len(cases)}"
    for c in cases:
        assert c.scenario == "记忆召回", c.sample_id
        assert any(c.sub_scenario.startswith(m) for m in MEMORY_MODES), c.sub_scenario


def test_memory_suite_rubric_and_scoring_points():
    for c in _memory_cases():
        assert c.rubric.multi_turn_consistency is not None, c.sample_id
        assert c.rubric.multi_turn_consistency.max >= 2, c.sample_id
        assert len(c.scoring_points) >= 3, c.sample_id
        assert len([t for t in c.turns if t.role == "user"]) >= 3, c.sample_id


def test_memory_mode_coverage():
    cases = _memory_cases()
    seen = {m for c in cases for m in MEMORY_MODES if c.sub_scenario.startswith(m)}
    assert seen == set(MEMORY_MODES), f"五种题型须全覆盖，缺 {set(MEMORY_MODES) - seen}"
