"""核心数据模型 —— 全部用 Pydantic 校验，保证 YAML 用例的结构正确。

设计原则：
  * `TestCase` 是评测的最小单元，**所有运行期产物（响应、判分）都不修改它**。
  * `CaseResult` 持有一次执行的完整证据链：原始对话 + 各 judge 输出 + 最终结论。
  * `RunReport` 是一次完整评测的聚合，便于版本间 diff。
  * `FailureTag` 只记录评测基础设施故障；质量问题由八维分数和指南扣分表达。
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from .evaluation import EvaluationDimension


# ---------------------------------------------------------------------------
# 基础设施失败标签
# ---------------------------------------------------------------------------

class FailureTag(str, Enum):
    """不参与评分的基础设施错误标签。"""

    ADAPTER_ERROR = "adapter_error"

    @property
    def description(self) -> str:
        return "Adapter 调用全部重试均失败"

    @property
    def label_zh(self) -> str:
        return "调用失败"


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


class InitialUserProfile(BaseModel):
    """评测账号在首轮对话前写入的用户画像。"""

    model_config = ConfigDict(extra="forbid")

    nickname: str | None = Field(default=None, min_length=1, max_length=80)
    birthday: date | None = None
    gender: Literal["男", "女"] | None = None
    current_concern: Literal["breast_cancer", "breast_tumor"] | None = None
    medical: dict[str, Any] = Field(default_factory=dict)
    facts: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_dynamic_facts(self) -> "InitialUserProfile":
        if len(self.facts) > 50:
            raise ValueError("user_profile.facts 最多允许 50 个字段")
        if any(not key.strip() or len(key) > 80 for key in self.facts):
            raise ValueError("user_profile.facts 的 key 必须为 1..80 个字符")
        if len(self.model_dump_json(include={"facts"})) > 8_000:
            raise ValueError("user_profile.facts 总长度不能超过 8000 字符")
        return self


class LongTermMemory(BaseModel):
    """写入 cx-agent 统一 Timeline 的单条长期记忆。"""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=100)
    category: Literal[
        "medication",
        "side_effect",
        "symptom",
        "metric",
        "diet",
        "activity",
        "mood",
        "contraindication",
        "risk_flag",
        "daily_score",
        "other",
    ]
    label: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=400)
    recorded_date: date | None = None
    event_date: date | None = None
    importance: int = Field(default=5, ge=1, le=10, strict=True)
    memory_tier: Literal["event", "semantic"] = "event"


class CaseInitialState(BaseModel):
    """Case 自包含的评测账号初始化数据。"""

    model_config = ConfigDict(extra="forbid")

    user_profile: InitialUserProfile = Field(default_factory=InitialUserProfile)
    long_term_memories: list[LongTermMemory] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            self.user_profile == InitialUserProfile()
            and not self.long_term_memories
        )

    @model_validator(mode="after")
    def _reject_overwriting_memories(self) -> "CaseInitialState":
        identities = [(item.key, item.recorded_date) for item in self.long_term_memories]
        if len(identities) != len(set(identities)):
            raise ValueError("long_term_memories 的 key + recorded_date 不能重复")
        return self


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
    # 用例业务类型（如“bug修复”），仅供检索和报告定位，不参与八维评分。
    case_type: str = Field(default="", alias="type")

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
