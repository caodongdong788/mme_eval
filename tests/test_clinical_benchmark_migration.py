"""临床 benchmark 迁移套件回归（change adopt-clinical-benchmark-methodology）。

覆盖：
  * Phase 4 覆盖矩阵：30 单轮 + 8 多轮 + 12 对抗（D1–D10 + 2 补充探针）全部加载。
  * profile_match 按病程 taxonomy 路由（screening/symptom/pathology/treatment→knowledge；
    rehab/followup→rehab；adversarial→adversarial），用真实 config.yaml 的 scoring 段。
  * Phase 2 指南要点库：迁移用例的 scoring_points 带 guideline 锚点，ScoringPointJudge
    + compute_guideline_match_rate 跑通（LLM 调用打桩，不触网）。
  * 指南锚点均带版本（Phase 5 版本化要求）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from medeval.judges.scoring_point import (
    ScoringPointJudge,
    compute_guideline_match_rate,
)
from medeval.loader import load_cases
from medeval.models import ChatMessage, ConversationTrace
from medeval.reporter.scoring import resolve_profile

ROOT = Path(__file__).resolve().parent.parent
# 合并去重后为单一乳腺癌 benchmark（拍平到 cases/breast_cancer），
# 参见 OpenSpec change consolidate-breast-cancer-benchmark。
SUITE_DIR = "cases/breast_cancer"


def _scoring_cfg() -> dict:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    return cfg.get("scoring") or {}


def _load_suite():
    return load_cases(include=[SUITE_DIR], base_dir=ROOT)


def _by_id():
    return {c.sample_id: c for c in _load_suite()}


# ── Phase 4：覆盖矩阵 ───────────────────────────────────────────────────────


def test_full_coverage_counts():
    """合并去重后的单一 benchmark 计数（拍平到 cases/breast_cancer）。"""
    cases = _load_suite()
    ids = {c.sample_id for c in cases}
    # 合并后总量：30 单轮 + 8 多轮场景(mts) + 12 对抗(D) + 11 红旗 + 4 迁入对抗(adv)
    #            + 5 迁入多轮(mt_d) + 6 专题 + 8 population + 8 agent = 92
    assert len(cases) == 92, f"合并后单一套件应为 92 题，实得 {len(cases)}"

    single = [c for c in cases if c.sample_id.startswith("bc_y")]
    multi = [c for c in cases if c.sample_id.startswith("bc_mts")]
    adversarial = [c for c in cases if c.sample_id.startswith("bc_d")]
    red_flags = [c for c in cases if c.sample_id.startswith("bc_rf")]
    migrated_adv = [c for c in cases if c.sample_id.startswith("bc_adv")]
    migrated_mt = [c for c in cases if c.sample_id.startswith("bc_mt_d")]
    assert len(single) == 30, "30 道临床单轮用例 Y1–Y30 保留"
    assert len(multi) == 8, "8 套临床多轮场景保留"
    assert len(adversarial) == 12, "D1–D10 + 危机沟通/多轮自相矛盾两补充探针 = 12"
    assert len(red_flags) == 11, "11 道肿瘤急症红旗（含 P1 扩库 5 题）"
    assert len(migrated_adv) == 4, "诱导剂量/症状确诊/越病理结论/单轮停内分泌 4 道对抗已迁入"
    assert len(migrated_mt) == 5, "depth2/depth3 病理/红旗升级/多轮停药施压/depth5 长程记忆 5 道多轮已迁入"

    # 关键补充探针存在
    assert "bc_d2b_suicidal_ideation" in ids
    assert "bc_d6b_multiturn_contradiction" in ids
    # 6 道肿瘤急症红旗均已迁入
    for sid in (
        "bc_rf_febrile_neutropenia", "bc_rf_cord_compression", "bc_rf_brain_mets",
        "bc_rf_svc_syndrome", "bc_rf_inflammatory_bc", "bc_rf_hypercalcemia",
    ):
        assert sid in ids, f"红旗急症 {sid} 必须迁入"
    # 多轮红旗升级用例存在
    assert "bc_mt_d3_chemo_fever_escalate" in ids
    assert len([c for c in cases if c.sample_id.startswith("bc_agent")]) == 8


def test_no_core_safety_remains():
    """合并后 cases/ 仅余 breast_cancer，无 core_ 前缀 / _core_safety 残留。"""
    cases = _load_suite()
    assert not any(c.sample_id.startswith("core_") for c in cases), "不应残留 core_ 前缀用例"
    assert not (ROOT / "cases" / "_core_safety").exists(), "_core_safety/ 必须已删除"
    # cases/ 下应仅有 breast_cancer 一个子目录
    subdirs = {p.name for p in (ROOT / "cases").iterdir() if p.is_dir()}
    assert subdirs == {"breast_cancer"}, f"cases/ 下应仅有 breast_cancer/，实得 {subdirs}"
    # breast_cancer/ 下应已拍平（无嵌套子目录）
    nested = [p.name for p in (ROOT / "cases" / "breast_cancer").iterdir() if p.is_dir()]
    assert not nested, f"breast_cancer/ 应拍平为单层 YAML，残留嵌套目录 {nested}"


def test_red_flag_cases_resolve_red_flag_profile():
    """红旗 YAML 中 score_profile=red_flag 的用例加载后 profile 均为 red_flag。"""
    rf = [c for c in _load_suite() if c.sample_id.startswith("bc_rf")]
    assert len(rf) == 11
    for c in rf:
        assert c.score_profile.value == "red_flag", c.sample_id


def test_every_case_has_explicit_score_profile():
    """92 条用例 MUST 显式声明 score_profile（非 default）。"""
    allowed = {"red_flag", "adversarial", "knowledge", "rehab", "population", "agent"}
    for c in _load_suite():
        assert c.score_profile.value in allowed, c.sample_id


# ── profile_match 路由（用真实 config.yaml scoring 段）──────────────────────


@pytest.mark.parametrize(
    "sample_id, expected",
    [
        ("bc_y1_high_risk_lifestyle", "knowledge"),   # 预防/筛查
        ("bc_y6_painless_lump", "knowledge"),         # 症状
        ("bc_y12_calcification", "knowledge"),        # 病理
        ("bc_y16_bcs_vs_mastectomy", "knowledge"),    # 治疗
        ("bc_y21_post_op_diet", "rehab"),             # 康复
        ("bc_y26_followup_interval", "rehab"),        # 随访
        ("bc_d1_supplement_cure", "adversarial"),     # 对抗
        ("bc_d2b_suicidal_ideation", "adversarial"),
        ("bc_mts1_bcs_vs_mastectomy", "knowledge"),   # 多轮·治疗
        ("bc_mts4_arm_rehab", "rehab"),               # 多轮·康复
        ("bc_mts8_followup_recurrence", "rehab"),     # 多轮·随访
    ],
)
def test_profile_routing(sample_id, expected):
    case = _by_id()[sample_id]
    assert case.score_profile.value == expected


# ── Phase 2：指南要点库 + ScoringPointJudge 跑通 ─────────────────────────────


def test_guideline_anchors_versioned():
    """所有带 guideline 锚点的得分点 MUST 含年份版本（Phase 5 版本化）。"""
    import re

    year = re.compile(r"(19|20)\d{2}")
    # 仅校验引用了具名权威指南机构的锚点须带版本年份；
    # 对抗题的「合格标准/原则」与三甲「流程示例」类锚点不属版本化指南，豁免。
    named_guideline = ("NCCN", "ASCO", "CACA", "中国抗癌协会")
    checked = 0
    for c in _load_suite():
        for sp in c.scoring_points:
            if not sp.guideline:
                continue
            if any(k in sp.guideline for k in named_guideline):
                assert year.search(sp.guideline), f"{c.sample_id} 指南锚点缺版本: {sp.guideline}"
                checked += 1
    assert checked > 30, "迁移套件应携带大量带版本的指南锚点"


def test_scoring_point_judge_and_guideline_match_on_migrated_case():
    """挑一道知识类迁移用例，stub ScoringPointJudge → 派生指南匹配率非空。"""
    case = _by_id()["bc_y5_familial_early_screening"]
    assert case.scoring_points, "知识类用例应有得分点"

    judge = ScoringPointJudge(enabled=True, provider="openai",
                              model="gpt-4o-mini", api_key="dummy")

    async def fake_call(prompt):
        # 全部得分点判为命中（met=True），1-based index。
        n = len(case.scoring_points)
        return {i: True for i in range(1, n + 1)}, {i: "stub" for i in range(1, n + 1)}

    judge._call = fake_call  # type: ignore[assignment]
    trace = ConversationTrace(
        messages=[
            ChatMessage(role="user", content=case.turns[0].content),
            ChatMessage(role="assistant", content="高危人群建议提前至30岁开始并增加乳腺核磁，请到遗传/乳腺专科。"),
        ]
    )
    verdicts = asyncio.run(judge.judge(case, trace))
    summary = next(v for v in verdicts if v.name == "scoring_point.summary")
    assert summary.passed  # 全命中 → 归一化 1.0
    rate = compute_guideline_match_rate(case, verdicts)
    assert rate is not None and rate == pytest.approx(1.0)
