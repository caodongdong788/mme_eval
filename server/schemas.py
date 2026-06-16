"""REST API 出入参 schema（Pydantic v2）。

敏感字段约定：``api_key`` 只在请求入参里出现、用于运行期，绝不出现在任何 *Out 响应或入库的
``judge_overrides`` / ``adapter_overrides`` 中。
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .datetime_json import ApiDateTime


# ---------------------------------------------------------------------------
# benchmark


class BenchmarkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    version: str
    source: str
    case_count: int
    tags: list[str]  # 该 benchmark 覆盖的 score_profile 列表（DB 列名保留 tags）
    levels: list[str] = Field(default_factory=list)
    created_by: Optional[str] = None
    created_at: Optional[ApiDateTime] = None


class BenchmarkUpdateRequest(BaseModel):
    """修改 benchmark 名称/描述（均可选，仅更新提供的字段）。"""

    name: Optional[str] = None
    description: Optional[str] = None


class RunRenameRequest(BaseModel):
    """评测 run 改名：空白名称非法，重名由后端校验。"""

    name: str


class CaseLogicOverride(BaseModel):
    """单条用例的判据覆盖（派生 benchmark 时按 sample_id 套用）。"""

    sample_id: str
    expected_behavior: Optional[dict[str, Any]] = None
    hard_gates: Optional[dict[str, Any]] = None
    rubric: Optional[dict[str, Any]] = None
    scoring_points: Optional[list[dict[str, Any]]] = None


class DeriveBenchmarkRequest(BaseModel):
    """从源 benchmark 派生一个含改后判据的新 benchmark（结构化覆盖）。"""

    name: str
    description: str = ""
    case_overrides: list[CaseLogicOverride] = Field(default_factory=list)


class DeriveBenchmarkYamlRequest(BaseModel):
    """从整段用例 YAML 派生新 benchmark（按 sample_id 只合并判据字段，未匹配丢弃）。"""

    name: str
    description: str = ""
    yaml_text: str


class OverwriteBenchmarkYamlRequest(BaseModel):
    """从整段用例 YAML 就地覆盖原 benchmark（合并语义同另存；内置不可覆盖）。"""

    yaml_text: str


class CasesYamlOut(BaseModel):
    """过滤命中用例的完整 YAML（供在线编辑器预填）。"""

    benchmark_id: int
    count: int
    yaml_text: str


class PreviewRejudgeRequest(BaseModel):
    """单用例 ephemeral 试判预览请求：携带该用例的判据覆盖。

    两种等价入参（优先 ``case_override``）：
    - ``case_override``：结构化覆盖（仅 4 个判据字段）；
    - ``yaml_text``：单条/多条用例 YAML（服务端按 sample_id 抽取该条的 4 个判据字段），
      便于前端直接复用 YAML 编辑器内容、无需客户端解析。
    二者皆空时按当前判据原样试判（对照）。``sample_id`` 一律以路径为准。
    """

    case_override: Optional[CaseLogicOverride] = None
    yaml_text: Optional[str] = None


class CaseScores(BaseModel):
    """单用例评分快照（用于试判前后对比；仅判分相关字段，不含会话/留痕）。"""

    hard_gate_passed: bool
    gate_passed: bool
    release_passed: bool
    composite_score: Optional[float] = None
    grade: str = ""
    dimension_scores: dict[str, Optional[float]] = Field(default_factory=dict)
    dimension_max: dict[str, float] = Field(default_factory=dict)
    score_profile: str = ""
    score_deductions: list[str] = Field(default_factory=list)
    failure_tags: list[str] = Field(default_factory=list)
    needs_human_review: bool = False
    verdicts: list[dict[str, Any]] = Field(default_factory=list)


class PreviewRejudgeResponse(BaseModel):
    """单用例试判预览结果：当前判定 vs 编辑判据后的新判定，及完整新 CaseResult。

    纯只读旁路：该响应**不代表任何已落库变化**——当前 run 的判分保持不变。
    """

    sample_id: str
    current: CaseScores
    preview: CaseScores
    changed: bool
    case_result: dict[str, Any]


class CaseBrief(BaseModel):
    """benchmark 用例清单条目（轻量预览）。"""

    sample_id: str
    scenario: str
    sub_scenario: str = ""
    level: str
    score_profile: str = "default"


# ---------------------------------------------------------------------------
# 发起评测


class JudgeOverride(BaseModel):
    """评测打分模型覆盖（现 gpt，可换更强模型）。api_key 仅运行期用，不入库。"""

    enabled: Optional[bool] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_version: Optional[str] = None
    api_key_env: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = None

    def public_dict(self) -> dict[str, Any]:
        """入库用：剔除 api_key 的非空字段。"""
        d = self.model_dump(exclude_none=True)
        d.pop("api_key", None)
        return d


class AdapterOverride(BaseModel):
    """被测 bot 可选覆盖。api_key 仅运行期用，不入库。"""

    model: Optional[str] = None
    base_url: Optional[str] = None
    system_prompt: Optional[str] = None
    api_key_env: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = None

    def public_dict(self) -> dict[str, Any]:
        d = self.model_dump(exclude_none=True)
        d.pop("api_key", None)
        return d


class RunCreate(BaseModel):
    benchmark_id: int
    run_name: Optional[str] = None
    # 按 level 过滤（如 ["L1","L3"]）；为空 = 全部 level。
    levels: list[str] = Field(default_factory=list)
    score_profiles: list[str] = Field(default_factory=list)
    limit: int = 0
    repeat: Optional[int] = Field(default=None, ge=1)
    judge: Optional[JudgeOverride] = None
    adapter: Optional[AdapterOverride] = None
    # 选用已保存的判分模型配置（连接信息 + Key 由服务端注入）；为空=沿用 config.yaml 默认。
    judge_model_id: Optional[int] = None


# ---------------------------------------------------------------------------
# 判分模型配置中心（全局共享；api_key 只写不读）


class JudgeModelOut(BaseModel):
    """判分模型配置读出：绝不含明文 api_key，仅以 has_api_key 掩码标记。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: str
    model: str
    base_url: str
    api_version: str
    temperature: Optional[float] = None
    pairwise_concurrency: int = 4
    has_api_key: bool
    created_by: Optional[str] = None
    created_at: Optional[ApiDateTime] = None


class JudgeModelCreate(BaseModel):
    name: str
    provider: str = "openai"
    model: str
    base_url: Optional[str] = None
    api_version: Optional[str] = None
    temperature: Optional[float] = None
    pairwise_concurrency: int = Field(default=4, ge=1)
    api_key: Optional[str] = None


class JudgeModelUpdate(BaseModel):
    """全字段可选；api_key 为 None=不变，非空=覆盖。"""

    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_version: Optional[str] = None
    temperature: Optional[float] = None
    pairwise_concurrency: Optional[int] = Field(default=None, ge=1)
    api_key: Optional[str] = None


class RejudgeRequest(BaseModel):
    """重判可选覆盖（全可选，无字段 = 复用源 run 配置重判）。

    覆盖仅作用于本次重判产出的新 run，不修改服务器 config.yaml。
    """

    # 覆盖 LLM judge 模型（provider/model/base_url/api_key…）；api_key 仅运行期、不入库。
    judge: Optional[JudgeOverride] = None
    # 选用已保存的判分模型配置（连接信息 + Key 由服务端注入）；为空=沿用源 run judge。
    judge_model_id: Optional[int] = None
    # 用该 benchmark 的用例判据按 sample_id 替换源 run 的冻结用例。
    cases_benchmark_id: Optional[int] = None
    # 仅重判上线判定失败（release_passed=false）的用例；通过用例沿用源结果，合并后重算。
    only_release_failed: bool = False


# ---------------------------------------------------------------------------
# run 输出


class RunSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_slug: str
    name: str
    status: str
    benchmark_id: Optional[int] = None
    adapter_type: str
    total: int
    passed: int
    pass_rate: float
    hard_gate_failed: int
    n_runs: int
    started_at: Optional[ApiDateTime] = None
    finished_at: Optional[ApiDateTime] = None
    created_at: Optional[ApiDateTime] = None
    error_msg: str = ""
    # 是否已落会话留痕（可离线重判/断点续跑）、是否置顶保护、重判/续跑的源 run
    has_traces: bool = False
    pinned: bool = False
    parent_run_id: Optional[int] = None


class RunDetailOut(RunSummaryOut):
    description: str = ""
    judge_overrides: dict[str, Any] = Field(default_factory=dict)
    adapter_overrides: dict[str, Any] = Field(default_factory=dict)
    grading: dict[str, Any] = Field(default_factory=dict)
    stability_distribution: dict[str, Any] = Field(default_factory=dict)
    latency_summary: dict[str, Any] = Field(default_factory=dict)
    token_summary: dict[str, Any] = Field(default_factory=dict)
    pass_rate_ci: dict[str, Any] = Field(default_factory=dict)
    guideline_match: dict[str, Any] = Field(default_factory=dict)
    failure_tag_counter: dict[str, Any] = Field(default_factory=dict)
    judge_fingerprints: dict[str, Any] = Field(default_factory=dict)
    by_level: dict[str, Any] = Field(default_factory=dict)
    by_scenario: dict[str, Any] = Field(default_factory=dict)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)


class ProgressOut(BaseModel):
    status: str
    progress: Optional[dict[str, Any]] = None


class ReviewSummary(BaseModel):
    """用例最新一条人审裁定摘要（用于列表列）。"""

    verdict: str  # agree | override
    reviewer: Optional[str] = None
    suggestion: Optional[str] = None
    comment: Optional[str] = None
    count: int = 0


class CaseRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sample_id: str
    scenario: str
    sub_scenario: str
    level: str
    hard_gate_passed: bool
    gate_passed: bool
    release_passed: bool
    composite_score: Optional[float] = None
    grade: str
    score_profile: str
    stability: str
    needs_human_review: bool
    guideline_match_rate: Optional[float] = None
    # 指南匹配命中/总数（服务端从 detail_json 派生；无带指南锚点得分点时为 None）。
    guideline_matched: Optional[int] = None
    guideline_total: Optional[int] = None
    latency_ms: Optional[float] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = None
    n_turns: int = 1
    failure_tags: list[str]
    review: Optional[ReviewSummary] = None
    # 该用例代表 trace 的 Langfuse 深链（追踪关闭/未配置/旧 run 时为 None）。仅用于前端跳转。
    langfuse_trace_url: Optional[str] = None


# ---------------------------------------------------------------------------
# 人工审核队列（HITL）


class AnnotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reviewer: Optional[str] = None
    verdict: str  # agree | override
    suggestion: Optional[str] = None
    comment: Optional[str] = None
    created_at: Optional[ApiDateTime] = None


class AnnotateRequest(BaseModel):
    """一条人工裁定。verdict 仅允许 agree / override。"""

    verdict: Literal["agree", "override"]
    suggestion: Optional[str] = None
    comment: Optional[str] = None


class ReviewQueueItemOut(BaseModel):
    """审核队列中的一条用例：用例摘要 + 入队原因 + 是否已审 + 已有裁定。"""

    sample_id: str
    scenario: str
    level: str
    release_passed: bool
    composite_score: Optional[float] = None
    failure_tags: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)  # needs_human_review/red_flag_failed/manual
    reviewed: bool = False
    annotations: list[AnnotationOut] = Field(default_factory=list)


class ReviewStatsOut(BaseModel):
    queue_total: int
    reviewed: int
    pending: int
    agree: int
    override: int
    agree_rate: float
    disagree_rate: float


# ---------------------------------------------------------------------------
# pairwise 对比（OpenSpec change add-pairwise-comparison）


class PairwiseCreate(BaseModel):
    """发起一次 Pairwise 对比：A=基线 run，B=本次 run，judge_model_id=裁判模型。"""

    run_a_id: int
    run_b_id: int
    judge_model_id: int
    scope: Literal["all", "divergent_only"] = "all"
    note: str = ""


class PairwiseNoteUpdate(BaseModel):
    """二次编辑对比备注：仅改 note。"""

    note: str = ""


class PairwiseComparabilityOut(BaseModel):
    """可比性校验结果：comparable=False 时 reasons 给中文原因。"""

    comparable: bool
    reasons: list[str] = Field(default_factory=list)
    subject_diff: dict[str, Any] = Field(default_factory=dict)


class PairwiseComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_a_id: int
    run_b_id: int
    run_a_name: Optional[str] = None
    run_b_name: Optional[str] = None
    note: str = ""
    judge_model: str
    judge_fingerprint: str
    status: str
    error_msg: str
    scope: str
    total_cases: int
    done_cases: int
    subject_diff: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[ApiDateTime] = None
    finished_at: Optional[ApiDateTime] = None


class PairwiseCalibrateUpdate(BaseModel):
    """人工校准覆写：结论 A|B|tie、三维度、理由。"""

    winner: Literal["A", "B", "tie"]
    dimension_winners: dict[str, Literal["A", "B", "tie"]] = Field(default_factory=dict)
    reason: str = ""


class PairwiseCaseVerdictOut(BaseModel):
    """有效值对外展示；机器原判仅在 human_calibrated 时回显 auto_*。"""

    sample_id: str
    scenario: str = ""
    sub_scenario: str = ""
    winner: str
    confidence_kind: Literal["high", "order", "safety", "human"]
    human_calibrated: bool = False
    swap_consistent: bool
    dimension_winners: dict[str, Any] = Field(default_factory=dict)
    reason: str
    order_runs: list[Any] = Field(default_factory=list)
    # 机器原判（仅已校准时有值，供对照）
    auto_winner: Optional[str] = None
    auto_confidence: Optional[str] = None
    auto_dimension_winners: Optional[dict[str, Any]] = None
    auto_reason: Optional[str] = None
    # 兼容旧字段：机器 confidence 原值
    confidence: str = "low"


class PairwiseDetailOut(PairwiseComparisonOut):
    """对比结果详情：汇总 + 逐用例列表。"""

    verdicts: list[PairwiseCaseVerdictOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# config / release thresholds


class ProfileCoverageOut(BaseModel):
    """该评分档对应的用例 score_profile 映射（用于前端展示覆盖范围）。"""

    is_fallback: bool = False
    score_profile: str = ""
    case_count: int = 0


class ReleaseThresholdItemOut(BaseModel):
    profile: str
    label: str
    max_total: float
    default_threshold: float
    override: Optional[float] = None
    effective: float
    coverage: ProfileCoverageOut = Field(default_factory=ProfileCoverageOut)


class ReleaseThresholdUpdateRequest(BaseModel):
    """按 profile 设置综合分上线阈值；值为 None 或等于默认 → 删除覆盖（恢复默认）。"""

    overrides: dict[str, Optional[float]]

