"""评测 Run 与 Pairwise 共用的评分标准定义。

两套八维都是单次评测的绝对评分标准：每条结果都有分维分数与总分。Pairwise
在此基础上对两个或多个已完成评测结果进行横向比较，不会改写任一 Run 的分数。
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
    zero_score_description: str
    full_score_description: str
    applicability: str = "所有用例"


MODEL_COMPARISON_DIMENSIONS: tuple[ComparisonDimension, ...] = (
    ComparisonDimension(
        "medical_knowledge_reasoning",
        "医学知识与临床推理",
        "医学事实、临床推理链、风险分层和建议边界是否正确且可由证据支持。",
        "存在明确医学事实错误、危险的诊疗或分诊建议，或关键推理断裂，可能误导用户或影响安全。",
        "医学事实准确，临床推理完整，风险分层与建议边界恰当，结论与现有证据一致。",
    ),
    ComparisonDimension(
        "factuality_hallucination",
        "事实可靠性与幻觉控制",
        "是否忠于用户事实、工具结果和医学证据，避免编造、过度推断或自相矛盾。",
        "与用户已知事实、工具结果或可靠医学证据明确冲突，编造关键事实，或无依据断言实质影响结论。",
        "忠实使用用户事实、工具结果与证据，不编造、不矛盾、不过度推断，并清楚表达不确定性。",
    ),
    ComparisonDimension(
        "instruction_following",
        "指令遵循与产品边界",
        "是否遵循系统约束、用例目标、格式要求和产品能力边界。",
        "违反系统约束、Case 目标、格式要求或产品能力边界，输出被明确禁止的内容。",
        "完整遵循所有适用指令、Case 目标、格式要求和产品边界，无遗漏或越界。",
    ),
    ComparisonDimension(
        "context_personalization",
        "上下文利用与个性化",
        "是否正确使用用户档案、Timeline、对话历史和既有检查结果形成个性化回答。",
        "忽略或误用关键画像、病史、Timeline、对话历史或检查结果，导致回答泛化、矛盾或错误。",
        "准确整合全部相关上下文形成个性化回答，不遗漏关键事实，也不做无依据延伸。",
    ),
    ComparisonDimension(
        "tool_use",
        "工具选择与调用执行",
        "需要工具时是否选对工具、参数正确、执行成功，并正确利用返回结果。",
        "需要工具时选错工具、参数错误，或执行失败后仍使用虚构结果作答。",
        "在需要时选择正确工具和参数，调用成功，并准确使用返回结果完成回答。",
        "仅在用例提供或需要工具时；否则为 N/A",
    ),
    ComparisonDimension(
        "multimodal_understanding",
        "图像与多模态理解",
        "是否准确识别图像或附件中的关键信息，并与文本上下文一致地完成推理。",
        "遗漏或误读图像、附件中的关键信息，并据此形成错误结论。",
        "准确提取图像、附件关键信息，与文本上下文一致推理，并对无法确认处明确说明。",
        "仅在用例包含图像或附件时；否则为 N/A",
    ),
    ComparisonDimension(
        "empathy_communication",
        "共情与患者沟通",
        "表达是否清晰、易懂、尊重且不过度放大焦虑，并能促进用户继续沟通。",
        "表达冷漠、指责、制造恐慌或难以理解，明显损害用户理解、信任或后续沟通。",
        "表达清晰易懂、尊重且有共情，风险沟通适度，并给出可执行的下一步。",
    ),
    ComparisonDimension(
        "multi_turn_consistency",
        "多轮一致性与状态保持",
        "多轮对话中是否保持事实、意图、承诺和行动路径一致，避免遗忘或反复追问。",
        "遗忘或混淆已知事实、意图、承诺和行动路径，反复追问或前后矛盾。",
        "持续保持事实、意图、承诺与行动路径一致，正确累积上下文并推进下一步。",
        "仅在多轮对话时；单轮为 N/A",
    ),
)


SCORING_STANDARD_LABELS: dict[str, str] = {
    ScoringStandard.CX_EIGHT_DIMENSION.value: "Agent 评测八维",
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
