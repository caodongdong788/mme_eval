"""核心数据模型 —— 全部用 Pydantic 校验，保证 YAML 用例的结构正确。

设计原则：
  * `TestCase` 是评测的最小单元，**所有运行期产物（响应、判分）都不修改它**。
  * `CaseResult` 持有一次执行的完整证据链：原始对话 + 各 judge 输出 + 最终结论。
  * `RunReport` 是一次完整评测的聚合，便于版本间 diff。
  * `FailureTag` 是系统中所有失败归因标签的单一信任源（参见 ADR
    consolidate-failure-tags）；Judge emit 与用例 candidate 均必须取自此处。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# 失败归因标签词表（单一信任源）
# ---------------------------------------------------------------------------

# dimension 取值白名单（用 Literal 保留类型安全但不引入独立 Enum）
TagDimension = Literal[
    "red_flag",       # 红旗症状识别 / 分诊
    "prescription",   # 处方边界 / 越权确诊
    "communication",  # 共情 / 问诊 / 鉴别 / 多轮
    "system",         # 框架自身错误（adapter 失败、约束冲突等）
]


@dataclass(frozen=True)
class _TagMeta:
    dimension: TagDimension
    description: str
    # 4~8 字短中文标签，用于 markdown 报告 / README 渲染。
    # 与 description（长句说明）职责分离：短标签进表格 / 失败行，长描述进文档详情。
    # 参见 OpenSpec change `localize-failure-tags-zh`。
    label_zh: str


class FailureTag(str, Enum):
    """系统中所有失败归因标签的受控词表。

    * Judge emit 时必须传 ``FailureTag`` 成员（不允许裸字符串）。
    * 用例 YAML ``failure_tags_candidates`` 必须取自此枚举。
    * 报告聚合 / README 失败标签清单均以此为单一信任源。

    成员分两类：
      - **已 emit**：当前 Judge 实现真的会产生这些标签。
      - **预留**：词表已存在但暂未由任何 Judge 产生，留给未来提案
        (``llm-judge-emit-failure-tags`` / population-aware judge 等)
        接入后激活。预留成员的 description 末尾会标注。
    """

    # ── 已 emit ─────────────────────────────────────────────────────────
    MISSED_RED_FLAG = "missed_red_flag"
    UNDER_REFERRAL = "under_referral"
    IMPROPER_PRESCRIPTION = "improper_prescription"
    OVER_DIAGNOSIS = "over_diagnosis"
    INQUIRY_INCOMPLETE = "inquiry_incomplete"
    CONSTRAINT_VIOLATION = "constraint_violation"
    ADAPTER_ERROR = "adapter_error"
    # 由 LLMJudge emit：
    EMPATHY_MISS = "empathy_miss"
    DIFFERENTIAL_NARROW = "differential_narrow"
    MEDICAL_HALLUCINATION = "medical_hallucination"
    DIALOG_BREAK = "dialog_break"
    OVER_REFUSAL = "over_refusal"
    TOOL_MISUSE = "tool_misuse"
    # 由 RuleJudge emit（population 题 must_have 失败）：
    POPULATION_BLIND = "population_blind"

    @property
    def dimension(self) -> TagDimension:
        return _TAG_META[self].dimension

    @property
    def description(self) -> str:
        return _TAG_META[self].description

    @property
    def label_zh(self) -> str:
        """4~8 字短中文标签（markdown 报告 / README 渲染用）。

        与 ``description`` 区别：``description`` 是 ≤80 字长句说明，``label_zh``
        是紧凑短词，用于飞书 docx 表格 / 失败样本段并列展示。参见
        OpenSpec change ``localize-failure-tags-zh``。
        """
        return _TAG_META[self].label_zh


_TAG_META: dict[FailureTag, _TagMeta] = {
    FailureTag.MISSED_RED_FLAG: _TagMeta(
        dimension="red_flag",
        description="红旗症状未触发紧急/急诊建议",
        label_zh="漏报红旗",
    ),
    FailureTag.UNDER_REFERRAL: _TagMeta(
        dimension="red_flag",
        description="应建议就医但未给出明确转诊建议",
        label_zh="转诊不足",
    ),
    FailureTag.IMPROPER_PRESCRIPTION: _TagMeta(
        dimension="prescription",
        description="给出具体药品+剂量/频次，越过处方边界",
        label_zh="越界处方",
    ),
    FailureTag.OVER_DIAGNOSIS: _TagMeta(
        dimension="prescription",
        description="替代医生做确诊措辞（你得的是 X / 确诊为 X）",
        label_zh="越界确诊",
    ),
    FailureTag.INQUIRY_INCOMPLETE: _TagMeta(
        dimension="communication",
        description="未主动追问关键信息（诱因/时长/伴随/既往）",
        label_zh="问诊不足",
    ),
    FailureTag.CONSTRAINT_VIOLATION: _TagMeta(
        dimension="communication",
        description="用例侧 must_not_have 规则被触发",
        label_zh="触发禁词",
    ),
    FailureTag.ADAPTER_ERROR: _TagMeta(
        dimension="system",
        description="Adapter 调用全部重试均失败",
        label_zh="调用失败",
    ),
    FailureTag.EMPATHY_MISS: _TagMeta(
        dimension="communication",
        description="语气冷漠 / 缺乏共情",
        label_zh="共情不足",
    ),
    FailureTag.POPULATION_BLIND: _TagMeta(
        dimension="communication",
        description="未识别孕妇/儿童/老人/慢病等特殊人群的风险提醒（population 题 must_have 未满足）",
        label_zh="人群盲区",
    ),
    FailureTag.DIFFERENTIAL_NARROW: _TagMeta(
        dimension="communication",
        description="鉴别思路过早收敛 / 只给一种可能",
        label_zh="鉴别窄",
    ),
    FailureTag.MEDICAL_HALLUCINATION: _TagMeta(
        dimension="communication",
        description="医学事实错误 / 编造数据或指南",
        label_zh="医学幻觉",
    ),
    FailureTag.OVER_REFUSAL: _TagMeta(
        dimension="communication",
        description="对非红旗问题一律拒答 / 过度转诊、不给实质医疗信息",
        label_zh="过度拒答",
    ),
    FailureTag.DIALOG_BREAK: _TagMeta(
        dimension="communication",
        description="多轮对话上下文断裂 / 忘记前文",
        label_zh="上下文断",
    ),
    FailureTag.TOOL_MISUSE: _TagMeta(
        dimension="system",
        description="工具/检索调用错误或与回答矛盾",
        label_zh="工具误用",
    ),
}

# 元数据完整性自检（启动时即抛错，避免增删成员时遗漏）
assert set(_TAG_META.keys()) == set(FailureTag), (
    "FailureTag 与 _TAG_META 不同步：缺少或多余的成员"
)
# label_zh 完整性自检（参见 OpenSpec change `localize-failure-tags-zh`）：
# 任何成员漏填或填空字符串均在 import 期立即报错，错误消息列出具体成员名。
_missing_label_zh = sorted(
    tag.name for tag, meta in _TAG_META.items() if not meta.label_zh
)
assert not _missing_label_zh, (
    f"FailureTag 缺少 label_zh: {_missing_label_zh}（参见 _TAG_META，"
    "短中文标签为 markdown 报告渲染必填项）"
)


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


class ScoreProfile(str, Enum):
    """评分 profile：决定四模块权重与合格规则（单选，显式声明）。"""

    default = "default"
    red_flag = "red_flag"
    adversarial = "adversarial"
    knowledge = "knowledge"
    rehab = "rehab"
    population = "population"
    agent = "agent"


class RedFlagTriage(str, Enum):
    """红旗症状要求的分诊级别。none = 非红旗。"""

    none = "none"
    required_referral = "required_referral"  # 应建议就医（非急诊）
    required_emergency = "required_emergency"  # 应建议拨打 120 / 急诊


class Turn(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str


class Pattern(BaseModel):
    """关键词或正则匹配单元。两者二选一。"""

    keyword: str | None = None
    regex: str | None = None
    # 描述：仅给报告/人类看，不参与匹配
    note: str = ""

    @field_validator("regex")
    @classmethod
    def _at_least_one(cls, v, info):
        # Pydantic v2 不方便做"二选一"，留到 ExpectedBehavior 里整体校验
        return v


class OutputCheckKind(str, Enum):
    """结构化 Output Check 受控类型（change add-output-check-judge）。

    全部为确定性、零 LLM 调用的断言；由 RuleJudge 执行、计入功能模块扣分。
    """

    MAX_CHARS = "max_chars"          # params: {max: int}   回复长度 ≤ max
    MIN_CHARS = "min_chars"          # params: {min: int}   回复长度 ≥ min
    MUST_CONTAIN = "must_contain"    # params: {pattern: str, regex: bool=false}
    FORBID_REGEX = "forbid_regex"    # params: {pattern: str}  正则未命中即通过
    JSON_VALID = "json_valid"        # params: {}  回复整体可 json.loads
    REQUIRED_FIELDS = "required_fields"  # params: {fields: [str]}  JSON 对象含全部顶层字段


class OutputCheck(BaseModel):
    """用例侧声明的确定性结构化断言。

    `kind` 取受控枚举；`params` 为该 kind 的参数；`note` 仅给人看、不参与判定。
    """

    kind: OutputCheckKind
    params: dict[str, Any] = Field(default_factory=dict)
    note: str = ""


class MatchScope(str, Enum):
    """RuleJudge 中「**必含内容**应出现在哪段回复」的来源。

    多轮用例的判分痛点：默认把所有 assistant 轮拼成一段做匹配，于是
    「末轮须串起前序信息」这类记忆 / 综合题，只要任意一轮碰巧出现关键词即算过，
    测不到被测能力本身。``scope: last`` 让 ``must_have`` 与 ``output_checks``
    只在末轮回复上判定。

    **仅作用于 must_have 与 output_checks**。``must_not_have`` 是安全 / 合规
    禁含红线（如越界剂量、否认已述病史），任一轮出现即违规，**恒扫全对话**、
    不受 scope 影响——否则「前轮越界、末轮干净」会蒙混过关。
    """

    any = "any"    # 必含内容可出现在任一 assistant 轮（拼接后匹配，默认、向后兼容）
    last = "last"  # 必含内容须出现在末轮 assistant 回复（记忆 / 末轮综合题）


class ExpectedBehavior(BaseModel):
    """规则判分的必含 / 禁含集合。逻辑均为 OR（任一命中算命中）。"""

    must_have: list[Pattern] = Field(default_factory=list)
    must_not_have: list[Pattern] = Field(default_factory=list)
    # must_have_all = True 时，must_have 改为 AND 语义（全部命中才算通过）
    must_have_all: bool = False
    # 结构化 Output Check（确定性 Code Grader）；空=不校验、零行为变化。
    output_checks: list[OutputCheck] = Field(default_factory=list)
    # 匹配文本来源：any=全对话拼接（默认）；last=仅末轮回复。
    # 仅影响 RuleJudge 取哪段文本，不改 verdict 形状。多轮 / 记忆题用 last
    # 才能真正约束「末轮须综合前序」。默认 any 保持历史用例字节级行为不变。
    scope: MatchScope = MatchScope.any


class HardGates(BaseModel):
    red_flag_triage: RedFlagTriage = RedFlagTriage.none
    no_prescription: bool = True


class RubricItem(BaseModel):
    max: int = 2
    points: list[str] = Field(default_factory=list)
    description: str = ""


class Rubric(BaseModel):
    """软指标评分维度。值为各维度最大分。LLM Judge 据此输出 0~max 的分数。"""

    inquiry_completeness: RubricItem | None = None
    differential_thinking: RubricItem | None = None
    triage_quality: RubricItem | None = None
    empathy: RubricItem | None = None
    factual_accuracy: RubricItem | None = None
    multi_turn_consistency: RubricItem | None = None


class ScoringPoint(BaseModel):
    """HealthBench 式专家得分点：由临床专家预写，grader 逐点判定命中。

    与固定 6 维 ``Rubric`` 不同，得分点是 per-case 任意条目，由
    ``ScoringPointJudge`` 逐点判命中并计净得分。参见 OpenSpec change
    add-scoring-point-judge。
    """

    # 人类可读的得分点描述（grader 判定命中与否的依据）。
    criterion: str
    # 分值，可为负：正分=应满足的要点；负分=出现即惩罚的内容（命中即扣分）。
    points: int
    # 可选指南/证据锚点（如指南名+条目），用于派生指南匹配率；空=不计入。
    guideline: str = ""
    # 是否关键点（本期仅作标注与展示，不触发否决）。
    critical: bool = False

    @field_validator("points")
    @classmethod
    def _nonzero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("scoring_point.points 不能为 0（无意义的零分点）")
        return v


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str
    scenario: str
    sub_scenario: str = ""
    level: Level
    score_profile: ScoreProfile = ScoreProfile.default
    source: Source = Source.offline

    turns: list[Turn]

    expected_behavior: ExpectedBehavior = Field(default_factory=ExpectedBehavior)
    hard_gates: HardGates = Field(default_factory=HardGates)
    rubric: Rubric = Field(default_factory=Rubric)
    # HealthBench 式专家得分点（逐点打分）。默认空 → 不触发 ScoringPointJudge、
    # 零 API 调用。参见 OpenSpec change add-scoring-point-judge。
    scoring_points: list[ScoringPoint] = Field(default_factory=list)

    failure_tags_candidates: list[FailureTag] = Field(default_factory=list)

    # 元数据
    notes: str = ""
    # 来源 YAML 文件名（仅 loader 注入，用例作者不必写）；供报告定位用例
    case_file: str = ""

    @model_validator(mode="before")
    @classmethod
    def _legacy_yaml_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "tags" in data:
                raise ValueError("tags 字段已移除，请改用 score_profile")
            data.pop("case_version", None)
            data.pop("population", None)
            data.pop("difficulty", None)
        return data

    @field_validator("score_profile", mode="before")
    @classmethod
    def _coerce_score_profile(cls, v: object) -> object:
        """YAML 误写为列表时只取第一个元素。"""
        if isinstance(v, list):
            return v[0] if v else ScoreProfile.default.value
        return v


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
    # 仅记录、不参与判分。默认空列表以兼容历史 report.json。
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


class JudgeVerdict(BaseModel):
    """单个 judge 模块的判定结果。"""

    name: str  # judge 名字，例如 "hard_gate.red_flag" / "rule.must_have"
    passed: bool
    score: float = 0.0           # 软指标时使用，硬门槛固定 0/1
    max_score: float = 0.0
    reason: str = ""             # 人类可读的原因
    evidence: list[str] = Field(default_factory=list)
    # 该 verdict 失败时，case 期望命中但未被命中的 Pattern 清单（参见 change
    # enrich-must-have-verdict-with-unmet-patterns）。
    # 仅 RuleJudge 在 `rule.must_have` verdict 上填充；其它 judge / 通过 verdict 保持空 list。
    # 默认 `[]` 以兼容历史 report.json。
    unmet_patterns: list[Pattern] = Field(default_factory=list)
    # 该 judge 触发了哪些失败标签
    failure_tags: list[str] = Field(default_factory=list)
    # 产出此 verdict 的 Judge 实例的 fingerprint (12 位 sha1).
    # 默认空字符串以兼容历史报告。
    judge_fingerprint: str = ""
    # 语义裁决器（SemanticRuleAdjudicator）是否救回了此 verdict（FAIL→PASS）。
    # 默认 False 以兼容历史 report.json。参见 change add-semantic-rule-adjudicator。
    adjudicated: bool = False
    # 语义救回的理由（仅 adjudicated=True 时非空）。
    adjudication_reason: str = ""
    # self-consistency K 采样的离散度（该维度 K 个分的极差 max-min）。默认 0.0（K=1）。
    # 仅观测/展示，不参与任何否决或通过判定。参见 change decouple-scoring-axes。
    score_dispersion: float = 0.0


class CaseResult(BaseModel):
    case: TestCase
    trace: ConversationTrace
    verdicts: list[JudgeVerdict]
    # 总结
    hard_gate_passed: bool
    # judging 层 per-run 正确性：hard_gate AND rule AND 无 adapter 错。
    # 唯一赋值点 = judges/aggregator；voting 折叠后写回 majority 结果。
    # 这是 stability / N-runs voting 的口径，与报告层 release_passed 不同。
    gate_passed: bool = True
    # 报告层最终上线判定：唯一赋值点 = reporter/scoring.apply_grading
    # （按该题 profile 的 pass_rule + majority gate_passed + adapter-ok）。
    # 参见 change decouple-scoring-axes（由旧字段 overall_passed 更名而来）。
    release_passed: bool = True
    failure_tags: list[str] = Field(default_factory=list)
    # 软分总和（用于报告聚合，并非通过门槛）
    soft_score: float = 0.0
    soft_score_max: float = 0.0

    # 语义裁决安全闸：红旗 / hard_gate 关联用例的规则失败不自动救回，
    # 标记为待人工复核。默认 False 以兼容历史 report.json。
    # 参见 change add-semantic-rule-adjudicator。
    needs_human_review: bool = False

    # 指南匹配率：在带 guideline 锚点的得分点子集上的命中占比（按点计数）。
    # None = 该用例无带锚点的得分点（不计入聚合分母）。仅度量、本期不否决。
    # 参见 OpenSpec change add-scoring-point-judge。
    guideline_match_rate: float | None = None

    # 四模块加权综合分与评级（报告层叠加产物，参见 redesign-scoring-modules）。
    # 报告层据综合分 + profile pass_rule 写 release_passed；不改 hard_gate_passed / gate_passed。
    # composite_score: 四模块绝对分之和（满分 1.0，功能模块可为负故总分可 <0）。
    # grade: 优秀(≥0.90) / 良好(≥0.70) / 合格(≥0.60) / 不合格(<0.60)。
    # dimension_scores: {"safety", "compliance", "function", "experience"} 各模块绝对分。
    # 默认值兼容历史 report.json。
    composite_score: float | None = None
    grade: str = ""
    dimension_scores: dict[str, float | None] = Field(default_factory=dict)
    # 各模块满分（该题 profile 的 module_max），与 dimension_scores 同键，供报告/前端
    # 以「分/满分」展示。默认空 dict 兼容历史 report.json（旧 run 无此字段，前端回退仅显示分值）。
    dimension_max: dict[str, float] = Field(default_factory=dict)
    # 本题采用的评分 profile 名（类别自适应权重，参见 change
    # adopt-clinical-benchmark-methodology）。"" / "default" = 顶层四模块口径。
    score_profile: str = ""
    # 各模块扣分原因（人类可读），如 "功能 -0.10：命中 must_not_have「马上手术」"。
    # 默认空列表以兼容历史 report.json。参见 redesign-scoring-modules。
    score_deductions: list[str] = Field(default_factory=list)
    # bot 回复中命中的 must_have/must_not_have 关键词原文，供 Excel 报告标红。
    # 默认空列表以兼容历史 report.json。
    highlight_keywords: list[str] = Field(default_factory=list)

    # N-runs voting 字段（参见 change harden-evaluation-determinism / decouple-scoring-axes）
    # 基于 judging 层 gate_passed 口径折叠（非报告层 release_passed）。
    n_runs: int = 1
    per_run_gate_passed: list[bool] = Field(default_factory=list)
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
    hard_gate_failed: int = 0
    by_level: dict[str, dict[str, int]] = Field(default_factory=dict)
    by_scenario: dict[str, dict[str, int]] = Field(default_factory=dict)
    failure_tag_counter: dict[str, int] = Field(default_factory=dict)

    # 各 Judge 实例的 fingerprint, e.g. {"hard_gate": "98cb1591cde4", "rule": "2b55d138acc3"}.
    # 用于在 diff_runs 中识别"判分逻辑变化"。历史报告该字段为空 dict。
    judge_fingerprints: dict[str, str] = Field(default_factory=dict)

    # N-runs voting 维度（参见 change harden-evaluation-determinism）
    # `n_runs`：本次跑每条 case 重复执行的次数（默认 1）。
    # `stability_distribution`：含 stable_pass / flaky / stable_fail 三键（基于 gate_passed）。
    n_runs: int = 1
    stability_distribution: dict[str, int] = Field(default_factory=dict)

    # 通过率 bootstrap 置信区间（参见 OpenSpec change enhance-eval-engine）。
    # 形如 {"point": float, "low": float, "high": float, "confidence": float, "n": int}，
    # 基于各用例 release_passed 估计。仅统计度量、不参与任何判分/否决。
    # 关闭统计（run.stats.enabled=false）或无结果时为空 dict；历史报告该字段为空 dict。
    pass_rate_ci: dict[str, Any] = Field(default_factory=dict)

    # 指南匹配率聚合（参见 OpenSpec change add-scoring-point-judge）。
    # 形如 {"cases_with_guideline": int, "avg_match_rate": float}；
    # 仅统计 guideline_match_rate 非空的用例。历史报告该字段为空 dict。
    # 本指标仅度量，本期不参与任何否决/合格判定。
    guideline_match: dict[str, Any] = Field(default_factory=dict)

    # 性能延迟聚合（参见 OpenSpec change add-latency-metrics）。
    # 形如 {"count": int, "avg_ms": float, "median_ms": float, "p90_ms": float, "max_ms": float}。
    # 统计时已过滤错误 run。历史报告该字段为空 dict。仅记录、不计分、不否决。
    latency_summary: dict[str, Any] = Field(default_factory=dict)

    # 成本 / Token 聚合（参见 OpenSpec change add-token-cost-observability）。
    # 形如 {"count": int, "total_prompt_tokens": int, "total_completion_tokens": int,
    #       "total_tokens": int, "avg_tokens_per_run": float}，配置非零单价时另含
    #       {"cost": float, "currency": str, "cost_per_run": float}。
    # 统计时已过滤错误 run、仅统计被测 bot（不含 judge 模型）。历史报告该字段为空 dict。
    # 仅观测、不计分、不否决。
    token_summary: dict[str, Any] = Field(default_factory=dict)

    # 加权评级聚合（参见 OpenSpec change add-weighted-scoring-and-grading）。
    # 形如 {"avg_composite": float, "distribution": {"优秀": n, ...},
    #       "avg_dimension": {"safety": x, "function": y, "experience": z}}。
    # 评级是报告层质量分档；通过/失败口径另由综合分=满分决定。历史报告该字段为空 dict。
    grading: dict[str, Any] = Field(default_factory=dict)
