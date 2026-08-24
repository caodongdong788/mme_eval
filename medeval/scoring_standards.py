"""评测 Run 与 Pairwise 共用的评分标准定义。

``cx_eight_dimension`` 继续服务 cx-agent 上线质量判断；
``model_comparison`` 只服务不同基座模型的相对能力对比，不改写主评测分数或门禁。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .evaluation import DIMENSION_LABELS, EvaluationDimension, dimension_standard_text


class ScoringStandard(StrEnum):
    CX_EIGHT_DIMENSION = "cx_eight_dimension"
    MODEL_COMPARISON = "model_comparison"


@dataclass(frozen=True)
class ComparisonDimension:
    key: str
    label: str
    description: str
    applicability: str = "所有用例"


MODEL_COMPARISON_DIMENSIONS: tuple[ComparisonDimension, ...] = (
    ComparisonDimension(
        "medical_knowledge_reasoning",
        "医学知识与临床推理",
        "医学事实、临床推理链、风险分层和建议边界是否正确且可由证据支持。",
    ),
    ComparisonDimension(
        "factuality_hallucination",
        "事实可靠性与幻觉控制",
        "是否忠于用户事实、工具结果和医学证据，避免编造、过度推断或自相矛盾。",
    ),
    ComparisonDimension(
        "instruction_following",
        "指令遵循与产品边界",
        "是否遵循系统约束、用例目标、格式要求和产品能力边界。",
    ),
    ComparisonDimension(
        "context_personalization",
        "上下文利用与个性化",
        "是否正确使用用户档案、Timeline、对话历史和既有检查结果形成个性化回答。",
    ),
    ComparisonDimension(
        "tool_use",
        "工具选择与调用执行",
        "需要工具时是否选对工具、参数正确、执行成功，并正确利用返回结果。",
        "仅在用例提供或需要工具时；否则为 N/A",
    ),
    ComparisonDimension(
        "multimodal_understanding",
        "图像与多模态理解",
        "是否准确识别图像或附件中的关键信息，并与文本上下文一致地完成推理。",
        "仅在用例包含图像或附件时；否则为 N/A",
    ),
    ComparisonDimension(
        "empathy_communication",
        "共情与患者沟通",
        "表达是否清晰、易懂、尊重且不过度放大焦虑，并能促进用户继续沟通。",
    ),
    ComparisonDimension(
        "multi_turn_consistency",
        "多轮一致性与状态保持",
        "多轮对话中是否保持事实、意图、承诺和行动路径一致，避免遗忘或反复追问。",
        "仅在多轮对话时；单轮为 N/A",
    ),
)


SCORING_STANDARD_LABELS: dict[str, str] = {
    ScoringStandard.CX_EIGHT_DIMENSION.value: "CX 八维评分",
    ScoringStandard.MODEL_COMPARISON.value: "模型对比八维",
}


def normalize_scoring_standard(value: str | ScoringStandard | None) -> str:
    raw = str(value or ScoringStandard.CX_EIGHT_DIMENSION.value)
    if raw not in SCORING_STANDARD_LABELS:
        return ScoringStandard.CX_EIGHT_DIMENSION.value
    return raw


def scoring_standard_label(value: str | ScoringStandard | None) -> str:
    return SCORING_STANDARD_LABELS[normalize_scoring_standard(value)]


def scoring_dimension_keys(value: str | ScoringStandard | None) -> tuple[str, ...]:
    standard = normalize_scoring_standard(value)
    if standard == ScoringStandard.MODEL_COMPARISON.value:
        return tuple(item.key for item in MODEL_COMPARISON_DIMENSIONS)
    return tuple(item.value for item in EvaluationDimension)


def scoring_dimension_labels(value: str | ScoringStandard | None) -> dict[str, str]:
    standard = normalize_scoring_standard(value)
    if standard == ScoringStandard.MODEL_COMPARISON.value:
        return {item.key: item.label for item in MODEL_COMPARISON_DIMENSIONS}
    return {item.value: DIMENSION_LABELS[item] for item in EvaluationDimension}


def scoring_dimension_criteria(value: str | ScoringStandard | None) -> str:
    standard = normalize_scoring_standard(value)
    if standard == ScoringStandard.MODEL_COMPARISON.value:
        return "\n".join(
            f"- {item.key}（{item.label}）：{item.description}适用范围：{item.applicability}。"
            for item in MODEL_COMPARISON_DIMENSIONS
        )
    return "\n".join(
        f"- {dimension_standard_text(dimension)}" for dimension in EvaluationDimension
    )


def scoring_dimension_values(value: str | ScoringStandard | None) -> tuple[str, ...]:
    if normalize_scoring_standard(value) == ScoringStandard.MODEL_COMPARISON.value:
        return ("1", "2", "tie", "na")
    return ("1", "2", "tie")


def all_scoring_dimension_keys() -> set[str]:
    return {
        *(dimension.value for dimension in EvaluationDimension),
        *(item.key for item in MODEL_COMPARISON_DIMENSIONS),
    }
