"""八维度 + 指南缺分扣减的报告层评分入口。

单题医生端 15 分、护士端 10 分、患者端 15 分，总分 40 分；医学安全性为 0 时总分归零。
本模块不读取权重、score profile 或历史四模块配置。
"""

from __future__ import annotations

from typing import Any

from ..evaluation import EvaluationDimension
from ..models import CaseResult, FailureTag
from .eight_dimension_scoring import score_eight_dimension_case, score_model_comparison_case
from ..scoring_standards import ScoringStandard, normalize_scoring_standard, scoring_dimension_keys

GRADE_EXCELLENT = "优秀"
GRADE_GOOD = "良好"
GRADE_PASS = "合格"
GRADE_FAIL = "不合格"

_DIMENSION_FAILURE_TAGS: dict[EvaluationDimension, FailureTag] = {
    EvaluationDimension.professional_accuracy: FailureTag.PROFESSIONAL_ACCURACY_GAP,
    EvaluationDimension.clinical_inquiry: FailureTag.CLINICAL_INQUIRY_GAP,
    EvaluationDimension.personalization: FailureTag.PERSONALIZATION_GAP,
    EvaluationDimension.plan_feasibility: FailureTag.PLAN_FEASIBILITY_GAP,
    EvaluationDimension.empathy: FailureTag.EMPATHY_GAP,
    EvaluationDimension.executability: FailureTag.EXECUTABILITY_GAP,
    EvaluationDimension.communication: FailureTag.COMMUNICATION_GAP,
}
_MAX_FAILURE_SUMMARY_TAGS = 3
_DERIVED_FAILURE_TAGS = {
    *(tag.value for tag in _DIMENSION_FAILURE_TAGS.values()),
    FailureTag.MEDICAL_SAFETY_RISK.value,
    FailureTag.GUIDELINE_COVERAGE_LOW.value,
    FailureTag.SCORE_BELOW_THRESHOLD.value,
    FailureTag.ASSERTION_FAILED.value,
}


def _sync_single_run_stability(result: CaseResult) -> None:
    """让单次评测的稳定性始终跟随最终运行验收结论。

    八维质量评分和运行断言都可能改变 ``release_passed``。单次评测不存在
    多次运行的波动空间，因此只要最终验收不通过，就不能保留旧的
    ``stable_pass``（反之亦然）。多次评测的稳定性由 ``fold_n_runs`` 按每次
    完整验收结果聚合，这里不覆盖它。
    """
    if int(result.n_runs or 1) != 1:
        return
    result.n_runs = 1
    result.per_run_passed = [bool(result.release_passed)]
    result.stability = "stable_pass" if result.release_passed else "stable_fail"


def score_case(
    result: CaseResult,
    scoring_standard: str | ScoringStandard | None = None,
) -> dict[str, Any]:
    """按本次 Run 选定的八维标准计算单条 Case 的绝对分。"""
    if normalize_scoring_standard(scoring_standard) == ScoringStandard.MODEL_COMPARISON.value:
        return score_model_comparison_case(result)
    return score_eight_dimension_case(result)


def _quality_failure_tags(
    result: CaseResult,
    breakdown: dict[str, Any],
    scoring_standard: str | ScoringStandard | None = None,
) -> list[str]:
    """按最终八维短板生成最多三个可行动摘要，不改变评分或通过门槛。"""
    if result.trace.error or breakdown["passed"]:
        return []

    if normalize_scoring_standard(scoring_standard) == ScoringStandard.MODEL_COMPARISON.value:
        return [FailureTag.SCORE_BELOW_THRESHOLD.value]

    raw = breakdown["raw_dimensions"]
    if raw.get(EvaluationDimension.medical_safety.value) != 5.0:
        # 安全门禁是最高优先级，避免再罗列次要体验问题制造噪声。
        return [FailureTag.MEDICAL_SAFETY_RISK.value]

    final = breakdown["dimensions"]
    ranked = sorted(
        (
            float(final.get(dimension.value, 0)),
            position,
            tag.value,
        )
        for position, (dimension, tag) in enumerate(_DIMENSION_FAILURE_TAGS.items())
        # 0～2 分代表该能力只有部分满足或基本不可用；指南缺分已经体现在
        # final 中，因此会自然归到它绑定的具体维度，不再产生模糊的覆盖率标签。
        if float(final.get(dimension.value, 0)) <= 2
    )
    tags = [tag for _score, _position, tag in ranked[:_MAX_FAILURE_SUMMARY_TAGS]]
    # 理论上整数八维评分低于 27 分时至少有一个维度 <=2；保留兜底只用于读取
    # 非标准历史分值，不让失败 Case 出现空摘要。
    return tags or [FailureTag.SCORE_BELOW_THRESHOLD.value]


def apply_grading(
    results: list[CaseResult],
    scoring_standard: str | ScoringStandard | None = None,
) -> None:
    """将最终评分就地写入 CaseResult。"""
    for result in results:
        standard = normalize_scoring_standard(scoring_standard)
        # Agent 在返回回答前已经执行失败时，没有可供质量 Judge 评分的内容。
        # 不得把 Judge 对空回答的兜底输出持久化成“40 分 / 优秀”等质量结论，
        # 否则既误导页面，也会污染运行汇总与后续归因。
        if result.trace.error:
            result.judge_error = False
            result.dimension_raw_scores = {}
            result.guideline_scores = []
            result.assertion_scores = []
            result.dimension_scores = {}
            result.dimension_max = {}
            result.end_scores = {}
            result.composite_score = None
            result.grade = "执行失败"
            result.score_deductions = [
                "未产生 Agent 回答：执行链路在对话完成前失败，本 Case 不参与质量评分。"
            ]
            result.medical_safety_passed = None
            result.release_passed = False
            result.failure_tags = list(dict.fromkeys([
                *result.failure_tags,
                FailureTag.ADAPTER_ERROR.value,
            ]))
            _sync_single_run_stability(result)
            continue
        breakdown = score_case(result, standard)
        # 八维评分与指南覆盖评分都属于判分环节。任一环节服务调用或 JSON
        # 解析失败时，结果不应被伪装为「0 分 / 不合格」；必须整体标记为
        # 判分异常，避免把系统故障误归因到 Agent。
        judge_error = result.judge_error or any(
            (verdict.name.startswith("dimension.") or verdict.name.startswith("guideline."))
            and bool(verdict.details.get("judge_error"))
            for verdict in result.verdicts
        )
        result.judge_error = judge_error
        result.dimension_raw_scores = breakdown["raw_dimensions"]
        result.guideline_scores = breakdown["guideline_scores"]
        result.assertion_scores = breakdown["assertion_scores"]
        result.dimension_scores = breakdown["dimensions"]
        result.dimension_max = breakdown["dimension_max"]
        result.end_scores = breakdown["ends"]
        result.composite_score = None if judge_error else breakdown["total"]
        result.grade = "判分异常" if judge_error else breakdown["grade"]
        result.score_deductions = breakdown["deductions"]
        # 已有 adapter/judge 故障标签保留；质量标签仅用于帮助定位不合格原因。
        quality_tags = [] if judge_error else _quality_failure_tags(result, breakdown, standard)
        assertion_tags = [
            FailureTag.ASSERTION_FAILED.value
            for verdict in result.verdicts
            if verdict.name.startswith("assertion.")
            and verdict.details.get("status") == "fail"
            and verdict.details.get("blocking", True)
        ]
        # 重判时清掉上一次由评分派生的标签再重新归纳，避免旧版泛化标签或已修复
        # 的短板一直残留；adapter_error 等执行链路标签仍然保留。
        retained_tags = [tag for tag in result.failure_tags if tag not in _DERIVED_FAILURE_TAGS]
        result.failure_tags = list(dict.fromkeys([*retained_tags, *quality_tags, *assertion_tags]))
        result.medical_safety_passed = (
            None
            if judge_error or standard == ScoringStandard.MODEL_COMPARISON.value
            else breakdown["raw_dimensions"].get(EvaluationDimension.medical_safety.value) == 5.0
        )
        blocking_assertion_failed = bool(assertion_tags)
        result.release_passed = (
            result.trace.error is None
            and bool(breakdown["passed"])
            and not judge_error
            and not blocking_assertion_failed
        )
        if blocking_assertion_failed:
            result.score_deductions = list(dict.fromkeys([
                *result.score_deductions,
                "关键可验证断言未满足：本用例不通过（不影响八维/指南分数）。",
            ]))
        _sync_single_run_stability(result)


def grading_summary(
    results: list[CaseResult],
    scoring_standard: str | ScoringStandard | None = None,
) -> dict[str, Any]:
    """聚合评级分布、平均总分、三端与八维平均分。"""
    distribution = {
        GRADE_EXCELLENT: 0,
        GRADE_GOOD: 0,
        GRADE_PASS: 0,
        GRADE_FAIL: 0,
    }
    totals: list[float] = []
    dimension_values = {dimension: [] for dimension in scoring_dimension_keys(scoring_standard)}
    end_values = {role: [] for role in ("doctor", "nurse", "user")}

    for result in results:
        if result.grade in distribution:
            distribution[result.grade] += 1
        if result.composite_score is not None:
            totals.append(float(result.composite_score))
        for dimension, values in dimension_values.items():
            if dimension in result.dimension_scores:
                values.append(float(result.dimension_scores[dimension]))
        for role, values in end_values.items():
            if role in result.end_scores:
                values.append(float(result.end_scores[role]))

    if not totals and not any(dimension_values.values()):
        return {}

    def averages(groups: dict[str, list[float]]) -> dict[str, float | None]:
        return {
            key: (sum(values) / len(values) if values else None)
            for key, values in groups.items()
        }

    return {
        "avg_composite": sum(totals) / len(totals) if totals else None,
        "distribution": distribution,
        "avg_dimension": averages(dimension_values),
        "avg_end": averages(end_values),
    }
