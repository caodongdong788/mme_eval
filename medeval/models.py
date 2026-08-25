"""核心数据模型 —— 全部用 Pydantic 校验，保证 YAML 用例的结构正确。

设计原则：
  * `TestCase` 是评测的最小单元，**所有运行期产物（响应、判分）都不修改它**。
  * `CaseResult` 持有一次执行的完整证据链：原始对话 + 各 judge 输出 + 最终结论。
  * `RunReport` 是一次完整评测的聚合，便于版本间 diff。
  * `FailureTag` 记录调用故障及由评分结果归纳出的质量失败类型，便于列表快速定位。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from .evaluation import EvaluationDimension


# ---------------------------------------------------------------------------
# 失败标签
# ---------------------------------------------------------------------------

class FailureTag(str, Enum):
    """不参与评分的失败摘要标签（评分本身仍由八维、指南和断言决定）。"""

    ADAPTER_ERROR = "adapter_error"
    MEDICAL_SAFETY_RISK = "medical_safety_risk"
    PROFESSIONAL_ACCURACY_GAP = "professional_accuracy_gap"
    CLINICAL_INQUIRY_GAP = "clinical_inquiry_gap"
    PERSONALIZATION_GAP = "personalization_gap"
    PLAN_FEASIBILITY_GAP = "plan_feasibility_gap"
    EMPATHY_GAP = "empathy_gap"
    EXECUTABILITY_GAP = "executability_gap"
    COMMUNICATION_GAP = "communication_gap"
    # 以下两项仅为历史报告兼容；新版失败摘要不再生成泛化的覆盖率/总分标签，
    # 而是直接指出指南扣分后的具体八维短板。
    GUIDELINE_COVERAGE_LOW = "guideline_coverage_low"
    SCORE_BELOW_THRESHOLD = "score_below_threshold"
    ASSERTION_FAILED = "assertion_failed"

    @property
    def description(self) -> str:
        return {
            self.ADAPTER_ERROR: "调用 CX Agent 接口多次重试后仍未获得有效回复",
            self.MEDICAL_SAFETY_RISK: "医学安全维度未通过，整题总分归零",
            self.PROFESSIONAL_ACCURACY_GAP: "医学专业准确性维度得分偏低",
            self.CLINICAL_INQUIRY_GAP: "关键临床追问覆盖不足",
            self.PERSONALIZATION_GAP: "未充分使用用户已经提供的相关信息",
            self.PLAN_FEASIBILITY_GAP: "方案未充分考虑临床可行性、患者条件或依从障碍",
            self.EMPATHY_GAP: "未准确识别并承接用户的具体情绪或努力",
            self.EXECUTABILITY_GAP: "缺少具体下一步、时机、步骤或反馈节点",
            self.COMMUNICATION_GAP: "表达不够清晰、简洁、自然或重点不突出",
            self.GUIDELINE_COVERAGE_LOW: "历史结果：Case 专属检查点总体命中偏低",
            self.SCORE_BELOW_THRESHOLD: "历史结果：综合得分未达到合格线",
            self.ASSERTION_FAILED: "可验证断言未满足",
        }[self]

    @property
    def label_zh(self) -> str:
        return {
            self.ADAPTER_ERROR: "Agent 执行失败",
            self.MEDICAL_SAFETY_RISK: "医学安全门禁失败",
            self.PROFESSIONAL_ACCURACY_GAP: "专业准确性与边界不足",
            self.CLINICAL_INQUIRY_GAP: "关键追问缺失",
            self.PERSONALIZATION_GAP: "用户信息利用不足",
            self.PLAN_FEASIBILITY_GAP: "方案可行性不足",
            self.EMPATHY_GAP: "情绪承接不足",
            self.EXECUTABILITY_GAP: "行动指引不清",
            self.COMMUNICATION_GAP: "表达沟通不佳",
            self.GUIDELINE_COVERAGE_LOW: "Case 专属要求未充分满足",
            self.SCORE_BELOW_THRESHOLD: "综合能力未达标",
            self.ASSERTION_FAILED: "关键验收项未满足",
        }[self]


# ---------------------------------------------------------------------------
# 用例侧 schema
# ---------------------------------------------------------------------------


class Level(str, Enum):
    L1 = "L1"  # 通用医学知识
    L2 = "L2"  # 业务场景
    L3 = "L3"  # 红旗回归
    L4 = "L4"  # 对抗集


class Source(str, Enum):
    """用例数据来源：线上真实流量 vs 线下构造。"""

    online = "online"    # 线上
    offline = "offline"  # 线下


class Turn(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str
    # ZIP benchmark 内的相对图片路径，例如 images/case-001-1.jpg。
    # 运行时由 loader 读取为 data URL，但原 YAML 路径始终保留在此字段。
    images: list[str] = Field(default_factory=list, max_length=10)
    _image_data_urls: list[str] = PrivateAttr(default_factory=list)

    @field_validator("images")
    @classmethod
    def _validate_images(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if len(normalized) != len(value):
            raise ValueError("turn.images 必须是非空相对图片路径列表")
        return normalized

    @property
    def image_data_urls(self) -> list[str]:
        """仅供 adapter 调用的已解析图片内容，不写入 YAML/report.json。"""
        return list(self._image_data_urls)

    def attach_image_data_urls(self, urls: list[str]) -> None:
        self._image_data_urls = list(urls)


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _validate_iso_datetime(value: str, field_name: str) -> str:
    normalized = value.strip()
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} 必须是 ISO 8601 日期时间") from exc
    return normalized


def _validate_optional_iso_datetime(value: str, field_name: str) -> str:
    return _validate_iso_datetime(value, field_name) if value.strip() else ""


class CaseResponsePreference(BaseModel):
    """评测账号预置的回复偏好。"""

    model_config = ConfigDict(extra="forbid")

    preference: str = Field(min_length=1, max_length=300)
    basis: str = Field(default="", max_length=400)


class CaseMedicalMetric(BaseModel):
    """病例夹中的一条结构化指标。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    value: float | None = None
    text_value: str = ""
    unit: str = Field(default="", max_length=40)
    is_trend_metric: bool = True
    measured_at: str = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def _validate_value(self) -> "CaseMedicalMetric":
        if self.value is None and not self.text_value.strip():
            raise ValueError("medical metric 必须填写 value 或 text_value")
        if not _is_iso_date(self.measured_at):
            raise ValueError("medical metric measured_at 必须是 YYYY-MM-DD")
        return self


class CaseMedicalDocument(BaseModel):
    """病例夹中的报告/病历及其结构化指标。"""

    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    document_date: str = Field(min_length=10, max_length=10)
    document_type: Literal["outpatient", "pathology", "imaging", "discharge", "lab", "other"] = "other"
    metrics: list[CaseMedicalMetric] = Field(default_factory=list)

    @field_validator("document_date")
    @classmethod
    def _validate_document_date(cls, value: str) -> str:
        if not _is_iso_date(value):
            raise ValueError("medical document document_date 必须是 YYYY-MM-DD")
        return value


class CaseHistoricalMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    created_at: str = ""

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: str) -> str:
        return _validate_optional_iso_datetime(value, "chat_history.messages.created_at")


class CaseHistoricalConversation(BaseModel):
    """在正式提问前已经存在于被测账号中的历史会话。"""

    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    started_at: str = ""
    messages: list[CaseHistoricalMessage] = Field(min_length=1)

    @field_validator("started_at")
    @classmethod
    def _validate_started_at(cls, value: str) -> str:
        return _validate_optional_iso_datetime(value, "chat_history.started_at")


class CaseScheduledTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1, max_length=80)
    task_name: str = Field(min_length=1, max_length=120)
    due_at: str = Field(min_length=1)
    message: str = Field(min_length=1)
    purpose: Literal[
        "intervention_completion_reminder", "medication_reminder", "review_reminder",
        "suggestion_action_reminder", "trend_card", "undercurrent_task",
        "undercurrent_care_plan", "cycle_self_exam", "custom",
    ] = "custom"
    time_source: Literal["user_explicit", "ai_inferred_default"] = "user_explicit"
    schedule_type: Literal["once", "cron"] = "once"
    cron_expression: str = ""
    timezone: str = "Asia/Shanghai"
    route: str = ""

    @field_validator("due_at")
    @classmethod
    def _validate_due_at(cls, value: str) -> str:
        return _validate_iso_datetime(value, "tool_state.scheduled_tasks.due_at")


class CaseCheckInRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1, max_length=80)
    category_key: str = Field(min_length=1, max_length=80)
    category_name: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=160)
    recorded_at: str = Field(min_length=1)
    values: dict[str, Any] = Field(default_factory=dict)
    fields: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("recorded_at")
    @classmethod
    def _validate_recorded_at(cls, value: str) -> str:
        return _validate_iso_datetime(value, "tool_state.check_ins.recorded_at")


class CaseUndercurrentTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1, max_length=80)
    kind: str = Field(min_length=1)
    status: str = "active"
    next_due_at: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int | None = None

    @field_validator("next_due_at")
    @classmethod
    def _validate_next_due_at(cls, value: str) -> str:
        return _validate_optional_iso_datetime(value, "tool_state.undercurrent_tasks.next_due_at")


class CaseToolState(BaseModel):
    """依赖真实业务表的工具初始化数据。"""

    model_config = ConfigDict(extra="forbid")

    scheduled_tasks: list[CaseScheduledTask] = Field(default_factory=list)
    check_ins: list[CaseCheckInRecord] = Field(default_factory=list)
    undercurrent_tasks: list[CaseUndercurrentTask] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.scheduled_tasks and not self.check_ins and not self.undercurrent_tasks


class CaseInitialState(BaseModel):
    """Case 自包含的评测账号初始化数据。

    Case 是标注格式，``user_profile`` 与 ``Timeline`` 均接受自由业务字段；
    仅在调用 cx-agent 时转换成其内部所需的结构。
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    user_profile: dict[str, Any] = Field(default_factory=dict)
    timeline: list[dict[str, Any]] | dict[str, Any] = Field(
        default_factory=list,
        validation_alias="Timeline",
        serialization_alias="Timeline",
    )
    profile_memory: list[str] = Field(default_factory=list, exclude_if=lambda value: not value)
    response_preferences: list[CaseResponsePreference] = Field(
        default_factory=list,
        max_length=3,
        exclude_if=lambda value: not value,
    )
    medical_documents: list[CaseMedicalDocument] = Field(
        default_factory=list,
        exclude_if=lambda value: not value,
    )
    chat_history: list[CaseHistoricalConversation] = Field(
        default_factory=list,
        exclude_if=lambda value: not value,
    )
    tool_state: CaseToolState = Field(
        default_factory=CaseToolState,
        exclude_if=lambda value: value.is_empty(),
    )

    def is_empty(self) -> bool:
        return (
            not self.user_profile
            and not self.timeline
            and not self.profile_memory
            and not self.response_preferences
            and not self.medical_documents
            and not self.chat_history
            and self.tool_state.is_empty()
        )

    def to_agent_payload(self) -> dict[str, Any]:
        """生成 cx-agent 可接受的初始化数据，不改变 Case 的原始画像。

        画像字段会进入 Agent 的事实画像；Timeline 的每个自由键值会转换为一条
        通用 Timeline 记录。Case 的自由字段及原始值不会被 schema 限制。
        """
        payload: dict[str, Any] = {}
        if self.user_profile:
            profile, facts = self._profile_to_agent_payload()
            if facts:
                profile["facts"] = facts
            payload["user_profile"] = profile
        memories = self._timeline_to_agent_memories()
        if memories:
            payload["long_term_memories"] = memories
        if self.profile_memory:
            payload["profile_memory"] = list(self.profile_memory)
        if self.response_preferences:
            payload["response_preferences"] = [
                item.model_dump(mode="json", exclude_none=True)
                for item in self.response_preferences
            ]
        if self.medical_documents:
            payload["medical_documents"] = [
                item.model_dump(mode="json", exclude_none=True)
                for item in self.medical_documents
            ]
        if self.chat_history:
            payload["chat_history"] = [
                item.model_dump(mode="json", exclude_none=True)
                for item in self.chat_history
            ]
        if not self.tool_state.is_empty():
            payload["tool_state"] = self.tool_state.model_dump(mode="json", exclude_none=True)
        return payload

    def _profile_to_agent_payload(self) -> tuple[dict[str, Any], dict[str, Any]]:
        raw = dict(self.user_profile)
        profile: dict[str, Any] = {}
        facts = raw.pop("facts", {})
        facts = dict(facts) if isinstance(facts, dict) else {"facts": facts}

        nickname = raw.pop("nickname", None)
        if isinstance(nickname, str) and nickname.strip():
            profile["nickname"] = nickname.strip()
        elif nickname is not None:
            facts["nickname"] = nickname

        birthday = raw.pop("birthday", None)
        if self._is_iso_date(birthday):
            profile["birthday"] = birthday
        elif birthday is not None:
            facts["birthday"] = birthday

        gender = raw.pop("gender", None)
        gender_aliases = {"男": "男", "男性": "男", "女": "女", "女性": "女"}
        if isinstance(gender, str) and gender in gender_aliases:
            profile["gender"] = gender_aliases[gender]
        elif gender is not None:
            facts["gender"] = gender

        concern = raw.pop("current_concern", None)
        concern_aliases = {
            "乳腺癌": "breast_cancer",
            "乳腺癌诊疗": "breast_cancer",
            "乳腺肿瘤诊疗": "breast_cancer",
            "乳腺肿瘤": "breast_tumor",
            "乳腺结节": "breast_tumor",
            "乳腺结节随访": "breast_tumor",
        }
        if isinstance(concern, str):
            facts.setdefault("当前关注", concern)
            internal_concern = concern_aliases.get(concern, concern)
            if internal_concern in {"breast_cancer", "breast_tumor"}:
                profile["current_concern"] = internal_concern
        elif concern is not None:
            facts["current_concern"] = concern

        medical = raw.pop("medical", None)
        if isinstance(medical, dict):
            profile["medical"] = medical
        elif medical is not None:
            facts["medical"] = medical
        facts.update(raw)
        return profile, facts

    def _timeline_to_agent_memories(self) -> list[dict[str, Any]]:
        entries = self.timeline if isinstance(self.timeline, list) else [self.timeline]
        memories: list[dict[str, Any]] = []
        supported_categories = {
            "medication", "side_effect", "symptom", "metric", "diet", "activity",
            "mood", "contraindication", "risk_flag", "daily_score", "other",
        }
        metadata_keys = {
            "key", "category", "label", "content", "note", "recorded_date", "event_date",
            "importance", "memory_tier", "日期", "时间", "date",
        }

        def add_memory(label: Any, content: Any, source: dict[str, Any] | None = None) -> None:
            source = source or {}
            category = source.get("category")
            memory = {
                "key": str(source.get("key") or f"case_timeline_{len(memories) + 1}"),
                "category": category if category in supported_categories else "other",
                "label": str(source.get("label") or label),
                "content": self._timeline_text(source.get("content", content)),
                "importance": source.get("importance") if isinstance(source.get("importance"), int) and 1 <= source["importance"] <= 10 else 5,
                "memory_tier": source.get("memory_tier") if source.get("memory_tier") in {"event", "semantic"} else "event",
            }
            for date_key in ("recorded_date", "event_date"):
                date_value = source.get(date_key)
                if date_value is not None:
                    rendered_date = str(date_value)
                    if self._is_iso_date(rendered_date):
                        memory[date_key] = rendered_date
                    else:
                        memory["content"] += f"\n{date_key}: {rendered_date}"
            memories.append(memory)

        for entry in entries:
            if not isinstance(entry, dict):
                add_memory("Timeline", entry)
            elif any(key in entry for key in {"label", "content", "key"}):
                add_memory(entry.get("label", "Timeline"), entry.get("content", entry), entry)
            else:
                for key, value in entry.items():
                    if key not in metadata_keys:
                        add_memory(key, value, entry)
        return memories

    @staticmethod
    def _timeline_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        import json
        return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))

    @staticmethod
    def _is_iso_date(value: Any) -> bool:
        return _is_iso_date(value)


class GuidelineItem(BaseModel):
    """一条可审计的指南扣分项。

    2.1 Case YAML 以 ``criteria`` 保存检查点，``deduction_rule`` 独立保存扣分
    规则，``reference_answers`` 保存供评审参考的好答案。旧版 ``criterion`` 与
    把扣分规则写在列表中的结构仍会在导入时归一。
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    dimension: EvaluationDimension
    # ``trigger`` 为空时，指南沿用“整段对话均适用”的语义；填写后先由 Judge 判断
    # 是否在实际对话中被触发。未触发的扣分项不参与分母、也绝不扣分。
    trigger: str = ""
    criteria: list[str] = Field(
        min_length=1,
        validation_alias=AliasChoices("criteria", "criterion"),
    )
    reference_answers: list[str] = Field(default_factory=list)
    deduction_rule: str = ""
    max_score: int = Field(ge=1, le=5, strict=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        legacy_criterion = normalized.pop("criterion", None)
        if "criteria" not in normalized and legacy_criterion is not None:
            normalized["criteria"] = legacy_criterion
        criteria = normalized.get("criteria")
        items = [criteria] if isinstance(criteria, str) else list(criteria or [])
        legacy_rule = next(
            (item for item in items if isinstance(item, str) and item.strip().startswith("扣分规则")),
            "",
        )
        if legacy_rule and not normalized.get("deduction_rule"):
            normalized["deduction_rule"] = legacy_rule
        if legacy_rule:
            normalized["criteria"] = [item for item in items if item != legacy_rule]
        return normalized

    @field_validator("criteria", mode="before")
    @classmethod
    def _normalize_criteria(cls, value: Any) -> list[str] | Any:
        # 简短 Case 仍可用单字符串；运行期统一按列表逐项核对。
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("criteria")
    @classmethod
    def _validate_criteria(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if len(normalized) != len(value) or not normalized:
            raise ValueError("guideline.criteria 必须是非空字符串或非空字符串列表")
        return normalized

    @field_validator("reference_answers", mode="before")
    @classmethod
    def _normalize_reference_answers(cls, value: Any) -> list[str] | Any:
        return [] if value is None else value

    @field_validator("reference_answers")
    @classmethod
    def _validate_reference_answers(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if len(normalized) != len(value):
            raise ValueError("guideline.reference_answers 必须是非空字符串列表或 null")
        return normalized

    @field_validator("trigger")
    @classmethod
    def _validate_trigger(cls, value: str) -> str:
        return value.strip()

    @field_validator("deduction_rule")
    @classmethod
    def _validate_deduction_rule(cls, value: str) -> str:
        return value.strip()

    @property
    def criterion(self) -> list[str]:
        """兼容内部旧调用；写回 YAML 时统一使用 2.1 的 ``criteria``。"""
        return self.criteria

    @property
    def checkpoints(self) -> list[str]:
        """供 judge 逐项判定的要求。"""
        return self.criteria

    @model_validator(mode="after")
    def _validate_semantics(self) -> "GuidelineItem":
        # 医学安全指南是允许的，但它不是普通的线性扣分项：一旦 Judge 判定有遗漏或
        # 相反表述，评分层会把 medical_safety 直接置 0，进而令整题归零。
        # 固定为 5 分，以便 YAML 中的“扣 5 分/医学安全性判 0 分”语义一致。
        if (
            self.dimension == EvaluationDimension.medical_safety
            and self.max_score != 5
        ):
            raise ValueError("medical_safety 指南的 max_score 必须为 5（违反即安全性判 0 分）")
        if not self.checkpoints:
            raise ValueError("guideline.criteria 至少需要一个检查点，不能只写扣分规则")
        return self


class DimensionCriteria(BaseModel):
    """单个八维维度的补充要求与好答案参考。"""

    model_config = ConfigDict(extra="forbid")

    criteria: list[str] = Field(min_length=1)
    reference_answers: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_list(cls, value: Any) -> Any:
        # 2.0 用例直接写 ``dimension: [criteria]``；2.1 改为对象结构。
        if isinstance(value, list):
            return {"criteria": value}
        return value

    @field_validator("criteria")
    @classmethod
    def _validate_criteria(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if len(normalized) != len(value) or not normalized:
            raise ValueError("dimension_criteria.criteria 必须是非空字符串列表")
        return normalized

    @field_validator("reference_answers", mode="before")
    @classmethod
    def _normalize_reference_answers(cls, value: Any) -> list[str] | Any:
        return [] if value is None else value

    @field_validator("reference_answers")
    @classmethod
    def _validate_reference_answers(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if len(normalized) != len(value):
            raise ValueError("dimension_criteria.reference_answers 必须是非空字符串列表或 null")
        return normalized


class CaseEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_criteria: dict[EvaluationDimension, DimensionCriteria] = Field(
        default_factory=dict
    )
    guidelines: list[GuidelineItem] = Field(default_factory=list)
    assertions: list["EvaluationAssertion"] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_content(self) -> "CaseEvaluation":
        for dimension, details in self.dimension_criteria.items():
            if not details.criteria:
                raise ValueError(f"dimension_criteria.{dimension.value}.criteria 不能为空")
        ids = [item.id for item in self.guidelines]
        if len(ids) != len(set(ids)):
            raise ValueError("evaluation.guidelines 的 id 必须在 Case 内唯一")
        assertion_ids = [item.id for item in self.assertions]
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("evaluation.assertions 的 id 必须在 Case 内唯一")
        return self


class EvaluationAssertion(BaseModel):
    """无需 LLM 判官、可由真实运行证据直接验证的一条断言。

    ``tool_call`` / ``retrieval`` 读 Langfuse 汇总，``transcript`` 核验回答要求。
    工具与数据命中属于运行验收项，
    可以阻断用例通过；只有明确绑定八维维度的 ``transcript`` 才会参与扣分。
    证据暂不可用时默认 ``warn``，不会把“没有接通追踪”误判为 Agent 失败。
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: Literal["tool_call", "retrieval", "transcript"]
    description: str = Field(min_length=1)
    blocking: bool = True
    on_unavailable: Literal["warn", "fail"] = "warn"
    # tool_call/retrieval：工具或来源标识。名称可对应 Langfuse 节点、摘要 action/source。
    name: str = ""
    # transcript：需出现的回答文字。
    contains: str = ""
    # exact 保留旧用例的逐字包含行为；semantic 由判分模型结合完整回答做语义核验。
    match_mode: Literal["exact", "semantic"] = "exact"
    min_count: int = Field(default=1, ge=1)
    # transcript：新版用例默认只检查 Agent 最终回答；旧 YAML 缺省时保留整段对话
    # 的历史行为，避免已有 benchmark 在升级后语义突变。
    scope: Literal["assistant_final", "assistant_messages", "full_conversation"] = "full_conversation"
    # transcript 可选进入两套评分标准；未配置时只作为运行验收。
    # ``dimension`` 是旧 YAML 的 Agent 评测八维单维字段；保存时统一写入
    # ``dimensions``，但读取旧用例仍完全兼容。
    dimension: EvaluationDimension | None = Field(default=None, exclude=True)
    # Agent 评测八维：未满足时按 deduction 从对应维度绝对分扣减。
    dimensions: list[str] = Field(default_factory=list, max_length=1)
    # 模型对比八维：与 Agent 评测八维一样，是一次评测可选的独立评分标准。
    # 未满足时从该标准对应维度的绝对分扣减；Pairwise 只比较已完成的评测结果。
    model_comparison_dimensions: list[str] = Field(default_factory=list, max_length=1)
    deduction: float = Field(default=0.0, ge=0, le=5)
    model_comparison_deduction: float = Field(default=0.0, ge=0, le=5)

    @model_validator(mode="before")
    @classmethod
    def _normalize_scoring_dimensions(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        selected = normalized.get("dimensions")
        legacy = normalized.get("dimension")
        if selected is None:
            normalized["dimensions"] = [legacy] if legacy else []
        elif isinstance(selected, str):
            normalized["dimensions"] = [selected]
        if normalized.get("dimensions") and not legacy:
            # 仅供历史读取方继续通过 assertion.dimension 获取首个关联维度；该字段
            # 不会再写回 YAML，规范结构只使用 dimensions。
            legacy_values = {item.value for item in EvaluationDimension}
            first = normalized["dimensions"][0]
            if first in legacy_values:
                normalized["dimension"] = first
        # 兼容上一版短暂写入的模型对比维度：当时它没有绝对扣分字段。升级后保留
        # 该选择，并以默认 1 分转成当前评分标准下的可执行扣分配置。
        if (
            normalized.get("model_comparison_dimensions")
            and "model_comparison_deduction" not in normalized
        ):
            normalized["model_comparison_deduction"] = 1
        # 回答要求一旦纳入维度扣分，就只应影响对应评分维度和总分。它与工具、
        # 数据命中等运行门禁的职责不同；否则会出现「扣 1 分但运行验收不合格」
        # 的矛盾结果。需要同时做文本门禁时，应另建一条未绑定评分维度的断言。
        if normalized.get("type") == "transcript" and (
            normalized.get("dimensions")
            or normalized.get("model_comparison_dimensions")
        ):
            normalized["blocking"] = False
        return normalized

    @field_validator("dimensions", "model_comparison_dimensions")
    @classmethod
    def _validate_dimensions(cls, value: list[str]) -> list[str]:
        from .scoring_standards import all_scoring_dimension_keys

        normalized = [str(item) for item in value]
        unknown = sorted(set(normalized) - all_scoring_dimension_keys())
        if unknown:
            raise ValueError(f"assertion 关联了未知评分维度：{', '.join(unknown)}")
        if len(normalized) != len(set(normalized)):
            raise ValueError("assertion.dimensions 不可重复选择同一维度")
        return normalized

    @model_validator(mode="after")
    def _validate_shape(self) -> "EvaluationAssertion":
        if self.type in {"tool_call", "retrieval"} and not self.name.strip():
            raise ValueError(f"assertion {self.id}: {self.type} 必须填写 name")
        if self.type == "transcript" and not self.contains.strip():
            raise ValueError(f"assertion {self.id}: transcript 必须填写 contains")
        if self.type != "transcript" and (
            self.dimensions
            or self.model_comparison_dimensions
            or self.deduction > 0
            or self.model_comparison_deduction > 0
        ):
            raise ValueError(f"assertion {self.id}: 只有 transcript 可绑定八维扣分")
        if self.type == "transcript" and bool(self.dimensions) != (self.deduction > 0):
            raise ValueError(
                f"assertion {self.id}: Agent 评测八维扣分需同时填写 dimensions 和 deduction"
            )
        if self.type == "transcript" and bool(self.model_comparison_dimensions) != (
            self.model_comparison_deduction > 0
        ):
            raise ValueError(
                f"assertion {self.id}: 模型对比八维扣分需同时填写 model_comparison_dimensions 和 model_comparison_deduction"
            )
        agent_dimensions = {item.value for item in EvaluationDimension}
        if set(self.dimensions) - agent_dimensions:
            raise ValueError(
                f"assertion {self.id}: dimensions 只能选择 Agent 评测八维的维度"
            )
        from .scoring_standards import scoring_dimension_keys
        model_dimensions = set(scoring_dimension_keys("model_comparison"))
        if set(self.model_comparison_dimensions) - model_dimensions:
            raise ValueError(
                f"assertion {self.id}: model_comparison_dimensions 只能选择模型对比八维的维度"
            )
        if (
            self.type == "transcript"
            and EvaluationDimension.medical_safety.value in self.dimensions
            and self.deduction not in {0, 5}
        ):
            raise ValueError(f"assertion {self.id}: medical_safety 回答要求扣分必须为 5（未满足即归零）")
        if (
            self.type == "transcript"
            and EvaluationDimension.medical_safety.value in self.dimensions
            and len(self.dimensions) > 1
        ):
            raise ValueError(f"assertion {self.id}: medical_safety 为安全门禁，不可与其他维度合并扣分")
        return self


class SimulatedUserTurn(BaseModel):
    """动态用户模拟器可发送的一条用户消息。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    role: Literal["user"] = "user"
    content: str = Field(min_length=1)
    images: list[str] = Field(default_factory=list, max_length=10)
    _image_data_urls: list[str] = PrivateAttr(default_factory=list)

    @property
    def image_data_urls(self) -> list[str]:
        return list(self._image_data_urls)

    def attach_image_data_urls(self, urls: list[str]) -> None:
        self._image_data_urls = list(urls)


class DynamicReplyRule(BaseModel):
    """由模拟用户模型按语义选择的确定用户回复。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    when: str = Field(min_length=1)
    reply: SimulatedUserTurn


class DynamicConversation(BaseModel):
    """模型语义决策、预设测试点兜底的多轮用户模拟计划。"""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["hybrid"] = "hybrid"
    max_turns: int = Field(default=3, ge=1, le=3)
    opening: SimulatedUserTurn
    reply_rules: list[DynamicReplyRule] = Field(default_factory=list)
    follow_ups: list[SimulatedUserTurn] = Field(default_factory=list, max_length=2)
    # 面向目标的模拟：不替代脚本化追问，而是在 Case 作者未写到的合理追问出现时，
    # 给模拟器一个明确的用户目标和可披露事实边界。
    user_goal: str = ""
    hidden_facts: dict[str, Any] = Field(default_factory=dict)
    completion_criteria: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def _validate_plan(self) -> "DynamicConversation":
        ids = [self.opening.id]
        ids.extend(rule.id for rule in self.reply_rules)
        ids.extend(rule.reply.id for rule in self.reply_rules)
        ids.extend(turn.id for turn in self.follow_ups)
        if len(ids) != len(set(ids)):
            raise ValueError("conversation 内的 turn/rule id 必须唯一")
        if len(self.follow_ups) + 1 > self.max_turns:
            raise ValueError("conversation.opening + follow_ups 不能超过 max_turns")
        return self


class TestCase(BaseModel):
    # 运行期 report.json 会以内部字段名序列化；同时接受 YAML 的 `type` 别名。
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["2.0", "2.1"]
    sample_id: str
    scenario: str
    level: Level
    source: Source = Source.offline
    # 用例业务类型（如“医学诊疗类”），仅供检索和报告定位，不参与八维评分。
    # 正式 YAML 字段为 case_type；读取既有数据时仍接受 type。
    case_type: str = Field(
        default="",
        validation_alias=AliasChoices("case_type", "type"),
        serialization_alias="case_type",
    )
    # 用例问题属性（如“产品优化”），仅供 Benchmark 检索、展示与报告定位，不参与评分。
    is_bug: str = ""

    initial_state: CaseInitialState = Field(
        default_factory=CaseInitialState,
        exclude_if=lambda value: value.is_empty(),
    )

    # 普通 Case 使用固定 turns；动态 Case 使用 conversation。两者不能同时为空。
    turns: list[Turn] = Field(default_factory=list)
    conversation: DynamicConversation | None = None

    evaluation: CaseEvaluation

    notes: str = ""
    # 线上飞书 Case 的结构化消息；普通离线 Case 不需要填写。
    rich_messages: list[dict[str, Any]] = Field(
        default_factory=list,
        exclude_if=lambda value: not value,
    )
    # 来源 YAML 文件名（仅 loader 注入，用例作者不必写）；供报告定位用例
    case_file: str = ""

    @model_validator(mode="after")
    def _validate_dialogue(self) -> "TestCase":
        if not self.turns and self.conversation is None:
            raise ValueError("Case 必须提供 turns 或 conversation")
        if self.turns:
            user_turns = sum(turn.role == "user" for turn in self.turns)
            # ``conversation`` 是动态用户模拟方案，受控于 3 轮以保证每题聚焦；
            # ``turns`` 则是导入的既有脚本式上下文，允许保留完整多轮会话，避免
            # 上传时静默截断标注数据。长会话会在发起评测页按用例数/轮数显式计入成本。
            if user_turns > 20:
                raise ValueError("固定脚本 Case 最多 20 个用户回合")
        return self

# ---------------------------------------------------------------------------
# 运行期数据
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ConversationTrace(BaseModel):
    """一次完整的 bot 交互证据链。"""

    messages: list[ChatMessage]
    # bot 端可能返回的工具调用、检索片段、内部 trace（结构化保留）
    raw_responses: list[dict[str, Any]] = Field(default_factory=list)
    # 整段会话总耗时（ms）。也作为性能延迟指标的"总耗时"来源。
    duration_ms: int = 0
    # 逐轮（每次 adapter 取得 bot 回复）的端到端耗时（ms），按轮次顺序。
    # 参见 OpenSpec change add-latency-metrics。
    turn_latencies_ms: list[float] = Field(default_factory=list)
    # 逐轮首个非空流式文本增量到达耗时（Time To First Token，ms）。
    # 非流式/历史 adapter 不提供时保持空列表；仅观测，不参与判分。
    turn_ttft_ms: list[float] = Field(default_factory=list)
    # 逐轮 token 用量（每个成功轮次一项），形如
    # {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}；
    # adapter 未返回 usage 的轮次记空 dict 占位。runner 在裁剪 raw_responses 之前当场抽取，
    # 故 store_raw=on_error 也不丢。仅观测、不参与判分。默认空列表兼容历史 report.json。
    # 参见 OpenSpec change add-token-cost-observability。
    turn_token_usage: list[dict[str, int]] = Field(default_factory=list)
    error: str | None = None
    # 该次执行（case/run）对应的 Langfuse trace 深链（自托管 base_url 拼链）。
    # 追踪关闭/未配置/旧 report.json 时为 None。仅观测、不参与判分。
    # 参见 OpenSpec change add-langfuse-per-case-trace-links。
    langfuse_trace_url: str | None = None
    # cx-agent 每个 HTTP turn 对应的内部 Langfuse trace id；多轮按首次出现顺序保留。
    langfuse_trace_ids: list[str] = Field(default_factory=list)
    # 评测完成时由 cx-agent 冻结的原生分享页。它独立于评测账号会话，账号清空后仍可回放。
    cx_evaluation_share_url: str | None = None
    # 评测结束、账号释放前从 cx-agent 测试审计接口固化的医学文献 RAG 原始命中。
    # Langfuse 可能截断工具输出；该快照保留完整 Top-K chunk 供 MME 长期审计。
    cx_literature_audits: list[dict[str, Any]] = Field(default_factory=list)
    # 审计接口是否已成功返回。空 audits 在该标记为真时表示 Agent 未触发文献检索，
    # 不是“尚未同步”；默认 False 兼容历史留痕和非 cx-agent adapter。
    cx_literature_audit_fetched: bool = False
    cx_literature_audit_error: str | None = None
    # 专用测试账号的领取/重置证据与请求前画像快照。仅观测、不参与判分。
    evaluation_identity: dict[str, Any] = Field(default_factory=dict)
    # 动态多轮的用户模拟留痕：本轮采用规则、原 Benchmark 脚本还是模型补全，
    # 以及模型在 Case 内复用的运行态事实。只用于回放/审计，不参与评分。
    simulation_trace: list[dict[str, Any]] = Field(default_factory=list)
    simulation_facts: dict[str, Any] = Field(default_factory=dict)
    # 从 Langfuse Public API 固化的 Agent/Generation/Tool 调用链快照。
    agent_chain: dict[str, Any] = Field(default_factory=dict)


class JudgeVerdict(BaseModel):
    """单个 judge 模块的判定结果。"""

    name: str  # dimension.<key> / guideline.<id>
    passed: bool
    score: float = 0.0
    max_score: float = 0.0
    reason: str = ""             # 人类可读的原因
    evidence: list[str] = Field(default_factory=list)
    # 指南 judge 的逐点命中、遗漏与实际扣分；其它 judge 默认为空。
    details: dict[str, Any] = Field(default_factory=dict)
    failure_tags: list[str] = Field(default_factory=list)
    judge_fingerprint: str = ""


class RunObservation(BaseModel):
    """一次 Case 试验的完整观测，保证延迟、Token 与错误状态使用同一口径。"""

    latency_ms: float = 0.0
    ttft_ms: float | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error: str | None = None


class CaseResult(BaseModel):
    case: TestCase
    trace: ConversationTrace
    verdicts: list[JudgeVerdict]
    # 总结
    # 没有医学安全 Gate 的评分标准使用 None，避免把“不适用”伪装成“通过”。
    medical_safety_passed: bool | None
    # 八维扣指南分后达 24/40 且 adapter 无错时通过。
    release_passed: bool = True
    # 八维判分服务调用失败时，分数不可用于质量结论。保留原始 verdict 便于排障，
    # 但列表与看板应明确展示“判分异常”，而非把它伪装成 0 分不合格。
    judge_error: bool = False
    failure_tags: list[str] = Field(default_factory=list)
    # 八维原始分、指南逐项分、指南扣分后的八维最终分、三端归一分。
    dimension_raw_scores: dict[str, float] = Field(default_factory=dict)
    guideline_scores: list[dict[str, Any]] = Field(default_factory=list)
    # 可评分的回答要求断言审计行；默认空以兼容历史 report.json。
    assertion_scores: list[dict[str, Any]] = Field(default_factory=list)
    composite_score: float | None = None
    grade: str = ""
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    dimension_max: dict[str, float] = Field(default_factory=dict)
    end_scores: dict[str, float] = Field(default_factory=dict)
    score_deductions: list[str] = Field(default_factory=list)

    # N-runs voting 基于每次完整的 release_passed 折叠。
    n_runs: int = 1
    per_run_passed: list[bool] = Field(default_factory=list)
    stability: Literal["stable_pass", "flaky", "stable_fail"] = "stable_pass"

    # 每次 run 的整段会话耗时（ms），长度对齐 n_runs（含错误 run，聚合时再过滤）。
    # 仅记录、不参与判分。默认空列表以兼容历史 report.json。
    # 参见 OpenSpec change add-latency-metrics。
    per_run_latency_ms: list[float] = Field(default_factory=list)

    # 每次 run 的平均轮次 TTFT（ms）；不支持流式采集或历史数据时为空。
    # 仅观测、不参与判分。
    per_run_ttft_ms: list[float] = Field(default_factory=list)

    # 每次 run 的会话总 token（由 trace.turn_token_usage 逐轮求和得到），长度对齐 n_runs
    # （含错误 run，聚合时再过滤）。仅观测、不参与判分。默认空列表以兼容历史 report.json。
    # 参见 OpenSpec change add-token-cost-observability。
    per_run_tokens: list[int] = Field(default_factory=list)
    # 新版统一观测结构。旧的三个 per_run_* 字段继续保留用于读取历史报告。
    per_run_observations: list[RunObservation] = Field(default_factory=list)

    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime = Field(default_factory=datetime.utcnow)


class RunReport(BaseModel):
    run_name: str
    description: str = ""
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime = Field(default_factory=datetime.utcnow)
    adapter_type: str = ""
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    results: list[CaseResult]

    # 聚合
    total: int = 0
    passed: int = 0
    medical_safety_failed: int = 0
    by_level: dict[str, dict[str, int]] = Field(default_factory=dict)
    by_scenario: dict[str, dict[str, int]] = Field(default_factory=dict)
    by_case_type: dict[str, dict[str, int]] = Field(default_factory=dict)
    failure_tag_counter: dict[str, int] = Field(default_factory=dict)

    # 八维和指南 Judge 实例的 fingerprint。
    judge_fingerprints: dict[str, str] = Field(default_factory=dict)

    # N-runs voting 维度（参见 change harden-evaluation-determinism）
    # `n_runs`：本次跑每条 case 重复执行的次数（默认 1）。
    # `stability_distribution`：含 stable_pass / flaky / stable_fail 三键。
    n_runs: int = 1
    stability_distribution: dict[str, int] = Field(default_factory=dict)

    # 通过率 bootstrap 置信区间。
    # 形如 {"point": float, "low": float, "high": float, "confidence": float, "n": int}，
    # 基于各用例 release_passed 估计。仅统计度量、不参与任何判分/否决。
    # 关闭统计（run.stats.enabled=false）或无结果时为空 dict。
    pass_rate_ci: dict[str, Any] = Field(default_factory=dict)

    # N-run 可靠性：pass_at_k 表示至少一次成功，pass_all_k 表示每次均成功。
    # 二者都只做可观测性与发布门禁输入，不改变单条 Case 的评分。
    reliability: dict[str, Any] = Field(default_factory=dict)

    # 指南得分率聚合；缺分已在单题评分中扣到绑定维度。
    guideline_match: dict[str, Any] = Field(default_factory=dict)

    # 性能延迟聚合。
    # 形如 {"count": int, "avg_ms": float, "median_ms": float, "p90_ms": float, "max_ms": float}。
    # 统计时已过滤错误 run。仅记录、不计分、不否决。
    latency_summary: dict[str, Any] = Field(default_factory=dict)

    # 流式首 Token 耗时聚合，结构与 latency_summary 一致。
    # 历史/非流式数据为空；仅观测、不计分、不否决。
    ttft_summary: dict[str, Any] = Field(default_factory=dict)

    # 成本 / Token 聚合。
    # 形如 {"count": int, "total_prompt_tokens": int, "total_completion_tokens": int,
    #       "total_tokens": int, "avg_tokens_per_run": float}，配置非零单价时另含
    #       {"cost": float, "currency": str, "cost_per_run": float}。
    # 统计时已过滤错误 run、仅统计被测 bot（不含 judge 模型）。
    # 仅观测、不计分、不否决。
    token_summary: dict[str, Any] = Field(default_factory=dict)

    # 固定八维评级聚合。
    # 形如 {"avg_composite": float, "distribution": {"优秀": n, ...},
    #       "avg_dimension": {"medical_safety": x, "professional_accuracy": y, ...}}。
    # 评级是报告层质量分档；合格及以上通过，医学安全性为 0 时整题归零。
    grading: dict[str, Any] = Field(default_factory=dict)
