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
    """不参与评分的失败归因标签（评分本身仍由八维与指南决定）。"""

    ADAPTER_ERROR = "adapter_error"
    MEDICAL_SAFETY_RISK = "medical_safety_risk"
    PROFESSIONAL_ACCURACY_GAP = "professional_accuracy_gap"
    CLINICAL_INQUIRY_GAP = "clinical_inquiry_gap"
    PERSONALIZATION_GAP = "personalization_gap"
    GUIDELINE_COVERAGE_LOW = "guideline_coverage_low"
    SCORE_BELOW_THRESHOLD = "score_below_threshold"

    @property
    def description(self) -> str:
        return {
            self.ADAPTER_ERROR: "调用 CX Agent 接口多次重试后仍未获得有效回复",
            self.MEDICAL_SAFETY_RISK: "医学安全维度未通过，整题总分归零",
            self.PROFESSIONAL_ACCURACY_GAP: "医学专业准确性维度得分偏低",
            self.CLINICAL_INQUIRY_GAP: "关键临床追问覆盖不足",
            self.PERSONALIZATION_GAP: "未充分使用 Case 中的用户档案",
            self.GUIDELINE_COVERAGE_LOW: "Case 指南项总体命中率偏低",
            self.SCORE_BELOW_THRESHOLD: "总分未达到合格阈值",
        }[self]

    @property
    def label_zh(self) -> str:
        return {
            self.ADAPTER_ERROR: "Agent 调用失败",
            self.MEDICAL_SAFETY_RISK: "医学安全风险",
            self.PROFESSIONAL_ACCURACY_GAP: "医学准确性不足",
            self.CLINICAL_INQUIRY_GAP: "关键追问不足",
            self.PERSONALIZATION_GAP: "用户档案未使用",
            self.GUIDELINE_COVERAGE_LOW: "指南覆盖不足",
            self.SCORE_BELOW_THRESHOLD: "总分未达标",
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

    def is_empty(self) -> bool:
        return not self.user_profile and not self.timeline

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
        if not isinstance(value, str):
            return False
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return False
        return True


class GuidelineItem(BaseModel):
    """一条可审计的指南扣分项。

    ``criterion`` 保留 Case YAML 的列表形态：除“扣分规则”外的每一项都是
    需要逐项核对的检查点；``max_score`` 表示该项最多可扣的分数。
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    dimension: EvaluationDimension
    criterion: list[str] = Field(min_length=1)
    max_score: int = Field(ge=1, le=5, strict=True)

    @field_validator("criterion", mode="before")
    @classmethod
    def _normalize_criterion(cls, value: Any) -> list[str] | Any:
        # 简短 Case 仍可用单字符串；运行期统一按列表逐项核对。
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("criterion")
    @classmethod
    def _validate_criterion(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if len(normalized) != len(value) or not normalized:
            raise ValueError("guideline.criterion 必须是非空字符串或非空字符串列表")
        return normalized

    @property
    def checkpoints(self) -> list[str]:
        """供 judge 逐项判定的要求，自动排除末尾的自然语言扣分规则。"""
        return [item for item in self.criterion if not item.startswith("扣分规则")]

    @property
    def deduction_rule(self) -> str:
        """Case 写在 criterion 内的自然语言扣分规则；省略时按线性扣分。"""
        return next((item for item in self.criterion if item.startswith("扣分规则")), "")

    @model_validator(mode="after")
    def _not_safety(self) -> "GuidelineItem":
        if self.dimension == EvaluationDimension.medical_safety:
            raise ValueError("guideline.dimension 不能为 medical_safety（二值安全底线）")
        if not self.checkpoints:
            raise ValueError("guideline.criterion 至少需要一个检查点，不能只写扣分规则")
        return self


class CaseEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_criteria: dict[EvaluationDimension, list[str]] = Field(
        default_factory=dict
    )
    guidelines: list[GuidelineItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_content(self) -> "CaseEvaluation":
        for dimension, criteria in self.dimension_criteria.items():
            if not criteria or any(not item.strip() for item in criteria):
                raise ValueError(f"dimension_criteria.{dimension.value} 必须是非空字符串列表")
        ids = [item.id for item in self.guidelines]
        if len(ids) != len(set(ids)):
            raise ValueError("evaluation.guidelines 的 id 必须在 Case 内唯一")
        return self


class TestCase(BaseModel):
    # 运行期 report.json 会以内部字段名序列化；同时接受 YAML 的 `type` 别名。
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["2.0"]
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

    turns: list[Turn]

    evaluation: CaseEvaluation

    notes: str = ""
    # 线上飞书 Case 的结构化消息；普通离线 Case 不需要填写。
    rich_messages: list[dict[str, Any]] = Field(
        default_factory=list,
        exclude_if=lambda value: not value,
    )
    # 来源 YAML 文件名（仅 loader 注入，用例作者不必写）；供报告定位用例
    case_file: str = ""

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
    # 专用测试账号的领取/重置证据与请求前画像快照。仅观测、不参与判分。
    evaluation_identity: dict[str, Any] = Field(default_factory=dict)
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


class CaseResult(BaseModel):
    case: TestCase
    trace: ConversationTrace
    verdicts: list[JudgeVerdict]
    # 总结
    medical_safety_passed: bool
    # 八维扣指南分后达 27/45 且 adapter 无错时通过。
    release_passed: bool = True
    failure_tags: list[str] = Field(default_factory=list)
    # 八维原始分、指南逐项分、指南扣分后的八维最终分、三端归一分。
    dimension_raw_scores: dict[str, float] = Field(default_factory=dict)
    guideline_scores: list[dict[str, Any]] = Field(default_factory=list)
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

    # 每次 run 的会话总 token（由 trace.turn_token_usage 逐轮求和得到），长度对齐 n_runs
    # （含错误 run，聚合时再过滤）。仅观测、不参与判分。默认空列表以兼容历史 report.json。
    # 参见 OpenSpec change add-token-cost-observability。
    per_run_tokens: list[int] = Field(default_factory=list)

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

    # 指南得分率聚合；缺分已在单题评分中扣到绑定维度。
    guideline_match: dict[str, Any] = Field(default_factory=dict)

    # 性能延迟聚合。
    # 形如 {"count": int, "avg_ms": float, "median_ms": float, "p90_ms": float, "max_ms": float}。
    # 统计时已过滤错误 run。仅记录、不计分、不否决。
    latency_summary: dict[str, Any] = Field(default_factory=dict)

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
