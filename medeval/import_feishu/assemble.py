"""RawRow → TestCase 组装。"""

from __future__ import annotations

from typing import Any

from ..models import TestCase, Turn
from .case_enrich import EnrichResult
from .sheet_parse import RawRow, parse_scoring_points


def _build_notes(row: RawRow) -> str:
    parts: list[str] = []
    if row.test_content:
        parts.append(f"测试内容：{row.test_content}")
    for rd in row.rounds:
        if rd.bot_reference:
            parts.append(f"[参考回复·第{rd.round_no}轮]\n{rd.bot_reference}")
    return "\n\n".join(parts).strip()


def _default_sample_id(row: RawRow, id_prefix: str, seq: int) -> str:
    return f"{id_prefix}{seq:03d}"


def build_test_case(
    row: RawRow,
    *,
    id_prefix: str,
    seq: int,
    enrich: EnrichResult | None = None,
    parsed_scoring_points: list[dict[str, Any]] | None = None,
) -> TestCase:
    """把单行 RawRow 与可选 enrich 结果组装为 TestCase。"""
    sample_id = (
        enrich.sample_id if enrich and enrich.sample_id else _default_sample_id(row, id_prefix, seq)
    )
    turns = [Turn(role="user", content=rd.user_text) for rd in row.rounds if rd.user_text]

    base: dict[str, Any] = {
        "sample_id": sample_id,
        "scenario": enrich.scenario if enrich else "导入",
        "sub_scenario": enrich.sub_scenario if enrich else "",
        "level": enrich.level if enrich else "L2",
        "score_profile": enrich.score_profile if enrich else "default",
        "source": "offline",
        "turns": [t.model_dump() for t in turns],
        "notes": enrich.notes if enrich and enrich.notes else _build_notes(row),
    }

    if enrich:
        base["expected_behavior"] = enrich.expected_behavior
        base["hard_gates"] = enrich.hard_gates
        if enrich.rubric:
            base["rubric"] = enrich.rubric
        if enrich.failure_tags_candidates:
            base["failure_tags_candidates"] = enrich.failure_tags_candidates

    sp = parsed_scoring_points
    if sp is None and enrich and enrich.scoring_points:
        sp = enrich.scoring_points
    if sp:
        base["scoring_points"] = sp

    if "expected_behavior" not in base:
        base["expected_behavior"] = {
            "must_have": [],
            "must_not_have": [],
            "output_checks": [],
        }
    if "hard_gates" not in base:
        base["hard_gates"] = {"no_prescription": True}

    return TestCase.model_validate(base)


def rows_to_cases(
    rows: list[RawRow],
    *,
    id_prefix: str,
    enrichments: list[EnrichResult | None] | None = None,
    parsed_points_list: list[list[dict[str, Any]] | None] | None = None,
) -> list[TestCase]:
    cases: list[TestCase] = []
    for i, row in enumerate(rows):
        enrich = enrichments[i] if enrichments else None
        parsed = parsed_points_list[i] if parsed_points_list else None
        if parsed is None and row.scoring_points_text.strip():
            parsed = parse_scoring_points(row.scoring_points_text)
        cases.append(
            build_test_case(
                row,
                id_prefix=id_prefix,
                seq=i + 1,
                enrich=enrich,
                parsed_scoring_points=parsed,
            )
        )
    return cases
