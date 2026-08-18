"""REST API 出入参 schema（Pydantic v2）。

敏感字段约定：``api_key`` 只在请求入参里出现、用于运行期，绝不出现在任何 *Out 响应或入库的
``judge_overrides`` / ``adapter_overrides`` 中。
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medeval.evaluation import EvaluationDimension

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
    tags: list[str]
    levels: list[str] = Field(default_factory=list)
    # 仅作为发起页的预设值；用户可在发起评测时覆盖。
    default_evaluation_mode: Literal["single_turn", "multi_turn"] = "single_turn"
    suite_type: Literal["capability", "regression"] = "capability"
    created_by: Optional[str] = None
    created_at: Optional[ApiDateTime] = None
    updated_at: Optional[ApiDateTime] = None


class BenchmarkUpdateRequest(BaseModel):
    """修改 benchmark 名称/描述（均可选，仅更新提供的字段）。"""

    name: Optional[str] = None
    description: Optional[str] = None


class RunRenameRequest(BaseModel):
    """评测 run 改名：空白名称非法，重名由后端校验。"""

    name: str


class CaseLogicOverride(BaseModel):
    """单条用例的八维关注点与指南覆盖。"""

    sample_id: str
    evaluation: Optional[dict[str, Any]] = None


class DeriveBenchmarkRequest(BaseModel):
    """从源 benchmark 派生一个含改后判据的新 benchmark（结构化覆盖）。"""

    name: str
    description: str = ""
    case_overrides: list[CaseLogicOverride] = Field(default_factory=list)


class DeriveBenchmarkYamlRequest(BaseModel):
    """从整段 V2 YAML 派生新 benchmark。"""

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
    """单用例试判预览，可覆盖 V2 ``evaluation``。"""

    case_override: Optional[CaseLogicOverride] = None
    yaml_text: Optional[str] = None


class CaseScores(BaseModel):
    """单用例评分快照（用于试判前后对比；仅判分相关字段，不含会话/留痕）。"""

    medical_safety_passed: bool
    release_passed: bool
    judge_error: bool = False
    composite_score: Optional[float] = None
    grade: str = ""
    dimension_scores: dict[str, Optional[float]] = Field(default_factory=dict)
    dimension_max: dict[str, float] = Field(default_factory=dict)
    dimension_raw_scores: dict[str, Optional[float]] = Field(default_factory=dict)
    end_scores: dict[str, float] = Field(default_factory=dict)
    guideline_scores: list[dict[str, Any]] = Field(default_factory=list)
    score_deductions: list[str] = Field(default_factory=list)
    failure_tags: list[str] = Field(default_factory=list)
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
    case_type: str = ""
    is_bug: str = ""
    level: str


class BenchmarkCaseYamlOut(BaseModel):
    benchmark_id: int
    sample_id: str
    case_file: str = ""
    yaml_text: str


class BenchmarkCaseYamlIn(BaseModel):
    yaml_text: str = Field(min_length=1)


class BenchmarkCaseContentOut(BaseModel):
    """供结构化用例编辑器读取的单条 Case 原始内容。"""

    benchmark_id: int
    sample_id: str
    case_file: str = ""
    case: dict[str, Any]


class BenchmarkCaseContentIn(BaseModel):
    """结构化编辑器保存的单条 Case；仍由后端完整校验后再落盘。"""

    case: dict[str, Any]


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
    enable_thinking: Optional[bool] = None

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
    # cx-agent 专用：本次评测是否暴露医学文献 RAG 工具。
    enable_rag: Optional[bool] = None

    def public_dict(self) -> dict[str, Any]:
        d = self.model_dump(exclude_none=True)
        d.pop("api_key", None)
        return d


class RunCreate(BaseModel):
    benchmark_id: int
    run_name: Optional[str] = None
    # single_turn = main 的固定 turns 逻辑；multi_turn = 动态用户模拟逻辑。
    evaluation_mode: Literal["single_turn", "multi_turn"] = "single_turn"
    # 按 level 过滤（如 ["L1","L3"]）；为空 = 全部 level。
    levels: list[str] = Field(default_factory=list)
    limit: int = 0
    repeat: Optional[int] = Field(default=None, ge=1)
    judge: Optional[JudgeOverride] = None
    adapter: Optional[AdapterOverride] = None
    # 选用已保存的判分模型配置（连接信息 + Key 由服务端注入）；为空=沿用 config.yaml 默认。
    judge_model_id: Optional[int] = None
    # 多轮对话的语义追问/模拟用户模型；为空则使用 config.yaml 默认配置。
    user_simulator: Optional[JudgeOverride] = None
    user_simulator_model_id: Optional[int] = None


class ScheduledEvaluationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    benchmark_id: int
    enabled: bool = True
    schedule_kind: Literal["daily", "weekly"] = "daily"
    schedule_time: str = "09:00"
    weekdays: list[int] = Field(default_factory=list)
    evaluation_mode: Literal["single_turn", "multi_turn"] = "single_turn"
    levels: list[str] = Field(default_factory=list)
    limit: int = Field(default=0, ge=0)
    repeat: int = Field(default=1, ge=1)
    enable_rag: bool = False
    enable_judge: bool = True
    judge_model_id: Optional[int] = None
    user_simulator_model_id: Optional[int] = None
    auto_attribution_enabled: bool = False
    auto_attribution_grades: list[Literal["优秀", "良好", "合格", "不合格"]] = Field(
        default_factory=list
    )
    auto_attribution_model_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def _schedule_name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("任务名称不能为空")
        return value

    @field_validator("schedule_time")
    @classmethod
    def _valid_schedule_time(cls, value: str) -> str:
        import re

        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("执行时间需为 HH:MM（24 小时制）")
        return value

    @model_validator(mode="after")
    def _validate_schedule(self) -> "ScheduledEvaluationCreate":
        if self.schedule_kind == "weekly":
            self.weekdays = sorted(set(self.weekdays))
            if not self.weekdays or any(day < 0 or day > 6 for day in self.weekdays):
                raise ValueError("每周执行至少选择一个有效星期")
        else:
            self.weekdays = []
        if not self.enable_judge and self.judge_model_id is not None:
            raise ValueError("未启用判分模型时不能选择打分模型")
        self.auto_attribution_grades = list(dict.fromkeys(self.auto_attribution_grades))
        if self.auto_attribution_enabled:
            if not self.enable_judge:
                raise ValueError("自动归因需要启用 LLM 判分")
            if not self.auto_attribution_model_id:
                raise ValueError("自动归因需要选择归因模型")
            if not self.auto_attribution_grades:
                raise ValueError("请至少选择一个自动归因的综合评价范围")
        return self


class ScheduledEvaluationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    benchmark_id: Optional[int] = None
    enabled: Optional[bool] = None
    schedule_kind: Optional[Literal["daily", "weekly"]] = None
    schedule_time: Optional[str] = None
    weekdays: Optional[list[int]] = None
    evaluation_mode: Optional[Literal["single_turn", "multi_turn"]] = None
    levels: Optional[list[str]] = None
    limit: Optional[int] = Field(default=None, ge=0)
    repeat: Optional[int] = Field(default=None, ge=1)
    enable_rag: Optional[bool] = None
    enable_judge: Optional[bool] = None
    judge_model_id: Optional[int] = None
    user_simulator_model_id: Optional[int] = None
    auto_attribution_enabled: Optional[bool] = None
    auto_attribution_grades: Optional[list[Literal["优秀", "良好", "合格", "不合格"]]] = None
    auto_attribution_model_id: Optional[int] = None


class ScheduledEvaluationOut(ScheduledEvaluationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    next_run_at: Optional[ApiDateTime] = None
    last_run_at: Optional[ApiDateTime] = None
    last_error: str = ""
    created_at: Optional[ApiDateTime] = None
    updated_at: Optional[ApiDateTime] = None
    created_by: Optional[str] = None


# ---------------------------------------------------------------------------
# OpenAPI：第三方自动发起评测


class OpenEvaluationCreate(BaseModel):
    """OpenAPI 发起评测的稳定入参，不接受任意连接地址或明文模型密钥。"""

    benchmark_id: int = Field(..., description="评测用例集 ID，可通过 GET /api/open/v1/benchmarks 查询")
    name: str = Field(..., min_length=1, max_length=200, description="本次评测名称，必须唯一")
    evaluation_mode: Literal["single_turn", "multi_turn"] = Field(
        default="single_turn", description="single_turn=固定对话；multi_turn=动态多轮对话"
    )
    enable_rag: bool = Field(default=False, description="是否向被测 CX Agent 开放医学文献 RAG")
    repeat: int = Field(default=1, ge=1, description="每个用例重复评测次数")
    levels: list[Literal["L1", "L2", "L3", "L4"]] = Field(
        default_factory=list, description="只评指定 Level；空数组表示评全部 Level"
    )
    enable_judge: bool = Field(default=True, description="是否启用八维与指南判分模型")
    judge_model_id: Optional[int] = Field(
        default=None, description="已保存判分模型 ID；为空时使用平台默认模型"
    )

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("评测名称不能为空")
        return value

    @model_validator(mode="after")
    def _judge_model_requires_judge(self) -> "OpenEvaluationCreate":
        if not self.enable_judge and self.judge_model_id is not None:
            raise ValueError("未启用判分模型时不能传 judge_model_id")
        return self


class OpenBenchmarkOut(BaseModel):
    id: int
    name: str
    description: str
    version: str
    case_count: int
    levels: list[str] = Field(default_factory=list)
    default_evaluation_mode: Literal["single_turn", "multi_turn"] = "single_turn"


class OpenJudgeModelOut(BaseModel):
    id: int
    name: str
    provider: str
    model: str
    has_api_key: bool


class OpenEvaluationResult(BaseModel):
    """评测成功后可用的运行汇总。"""

    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float


class OpenEvaluationGradeResult(OpenEvaluationResult):
    """已完成评测的逐用例评级分布。"""

    excellent_cases: int = 0
    good_cases: int = 0
    qualified_cases: int = 0
    unqualified_cases: int = 0
    other_cases: int = 0


class OpenEvaluationOut(BaseModel):
    id: int
    dashboard_url: str
    name: str
    status: str
    benchmark_id: int
    evaluation_mode: Literal["single_turn", "multi_turn"]
    repeat: int
    enable_rag: bool
    enable_judge: bool
    judge_model_id: Optional[int] = None
    # 仅 status=success 时返回；未完成或失败时严格为 null，避免读取中间统计。
    result: Optional[OpenEvaluationResult] = None
    progress: Optional[dict[str, Any]] = None
    queue_position: Optional[int] = None
    waiting_for_accounts: bool = False
    account_queue: dict[str, Any] = Field(default_factory=dict)
    error_msg: str = ""
    # 与评测总览页一致的聚合指标；不包含任何 Case、对话或调用链明细。
    avg_composite: Optional[float] = None
    avg_dimension: dict[str, Any] = Field(default_factory=dict)
    stability_distribution: dict[str, Any] = Field(default_factory=dict)
    latency_summary: dict[str, Any] = Field(default_factory=dict)
    ttft_summary: dict[str, Any] = Field(default_factory=dict)
    token_summary: dict[str, Any] = Field(default_factory=dict)
    reliability: dict[str, Any] = Field(default_factory=dict)
    pass_rate_ci: dict[str, Any] = Field(default_factory=dict)
    guideline_match: dict[str, Any] = Field(default_factory=dict)
    failure_tag_counter: dict[str, Any] = Field(default_factory=dict)
    by_level: dict[str, Any] = Field(default_factory=dict)
    by_scenario: dict[str, Any] = Field(default_factory=dict)
    by_case_type: dict[str, Any] = Field(default_factory=dict)


class OpenEvaluationBatchItem(BaseModel):
    id: int
    name: str
    status: str
    trigger_type: Literal["manual", "scheduled", "open_api"]
    benchmark_id: int
    dashboard_url: str
    created_at: Optional[ApiDateTime] = None
    finished_at: Optional[ApiDateTime] = None
    # 仅成功任务提供；其他状态不可把中间结果误当最终结果。
    result: Optional[OpenEvaluationGradeResult] = None
    error_msg: str = ""


class OpenEvaluationBatchOut(BaseModel):
    total: int
    items: list[OpenEvaluationBatchItem]


class OpenAttributionRecommendation(BaseModel):
    scope: str = ""
    priority: str = ""
    target: str = ""
    action: str = ""
    expected_effect: str = ""
    risk: str = ""
    verification: str = ""
    acceptance_criteria: str = ""


class OpenAttributionOptimizationClassification(BaseModel):
    domain: str = ""
    component: str = ""
    failure_mode: str = ""
    action_type: str = ""
    evidence_status: str = ""
    coverage_status: str = ""


class OpenAttributionDeduction(BaseModel):
    deduction_id: str
    dimension: str = ""
    severity: str = "medium"
    issue_type: str = "other"
    root_cause_stage: str = ""
    optimization_classification: OpenAttributionOptimizationClassification = Field(
        default_factory=OpenAttributionOptimizationClassification
    )
    finding: str = ""
    primary_cause: dict[str, Any] = Field(default_factory=dict)
    root_cause_test: dict[str, Any] = Field(default_factory=dict)
    rag_diagnosis: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[OpenAttributionRecommendation] = Field(default_factory=list)


class OpenAttributionCaseOptimization(BaseModel):
    summary: str = ""
    deductions: list[OpenAttributionDeduction] = Field(default_factory=list)
    recommendations: list[OpenAttributionRecommendation] = Field(default_factory=list)


class OpenAttributionCaseOut(BaseModel):
    sample_id: str
    scenario: str = ""
    case_type: str = ""
    status: str
    attempt_count: int = 0
    error_msg: str = ""
    attribution_available: bool = False
    started_at: Optional[ApiDateTime] = None
    finished_at: Optional[ApiDateTime] = None
    cx_agent_optimization: OpenAttributionCaseOptimization


class OpenAttributionCluster(BaseModel):
    cause_code: str = ""
    cause_label: str = ""
    owner: str = ""
    issue_type: str = "other"
    issue_types: list[str] = Field(default_factory=list)
    root_cause_stage: str = ""
    optimization_classification: OpenAttributionOptimizationClassification = Field(
        default_factory=OpenAttributionOptimizationClassification
    )
    sample_ids: list[str] = Field(default_factory=list)
    deduction_ids: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    case_count: int = 0
    deduction_count: int = 0
    priority: str = "P2"
    confidence: float = 0
    summary: str = ""
    examples: list[str] = Field(default_factory=list)
    recommendations: list[OpenAttributionRecommendation] = Field(default_factory=list)
    verification_plan: dict[str, Any] = Field(default_factory=dict)


class OpenAttributionTaskSummary(BaseModel):
    cx_agent_case_count: int = 0
    clusters: list[OpenAttributionCluster] = Field(default_factory=list)


class OpenAttributionTaskOut(BaseModel):
    id: int
    run_id: int
    run_name: str = ""
    report_url: str
    judge_model_id: int
    judge_model_name: str = ""
    status: str
    requested_count: int
    total_count: int
    skipped_count: int
    completed_count: int
    success_count: int
    failed_count: int
    error_msg: str = ""
    created_at: Optional[ApiDateTime] = None
    started_at: Optional[ApiDateTime] = None
    finished_at: Optional[ApiDateTime] = None
    cx_agent_optimization_summary: OpenAttributionTaskSummary
    cases: list[OpenAttributionCaseOut] = Field(default_factory=list)


class OpenAttributionTaskBatchOut(BaseModel):
    total: int
    items: list[OpenAttributionTaskOut]


class CaseAttributionOut(BaseModel):
    """单个用例的持久化 AI 归因；未生成时 analysis 为 null。"""

    available: bool = False
    stale: bool = False
    analysis: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttributionTaskCreate(BaseModel):
    sample_ids: list[str] = Field(min_length=1, max_length=100)
    judge_model_id: int = Field(gt=0)


class AttributionTaskRerun(BaseModel):
    sample_ids: list[str] = Field(min_length=1, max_length=100)
    judge_model_id: int = Field(gt=0)


class AttributionTaskResume(BaseModel):
    judge_model_id: int = Field(gt=0)


class AttributionTaskItemOut(BaseModel):
    sample_id: str
    scenario: str = ""
    case_type: str = ""
    status: str
    attempt_count: int = 0
    error_msg: str = ""
    attribution_available: bool = False
    attribution_stale: bool = False
    started_at: Optional[ApiDateTime] = None
    finished_at: Optional[ApiDateTime] = None


class AttributionTaskOut(BaseModel):
    id: int
    run_id: int
    judge_model_id: int
    judge_model_name: str = ""
    status: str
    requested_count: int
    total_count: int
    skipped_count: int
    completed_count: int
    success_count: int
    failed_count: int
    running_count: int = 0
    pending_count: int = 0
    error_msg: str = ""
    created_at: Optional[ApiDateTime] = None
    started_at: Optional[ApiDateTime] = None
    finished_at: Optional[ApiDateTime] = None
    diagnostic_summary: dict[str, Any] = Field(default_factory=dict)
    items: list[AttributionTaskItemOut] = Field(default_factory=list)


OpenApiPermission = Literal[
    "benchmarks:read",
    "judge_models:read",
    "evaluations:create",
    "evaluations:read",
    "attributions:read",
]


class OpenApiAccessKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    api_key: str
    key_prefix: str
    permissions: list[OpenApiPermission]
    created_by: Optional[str] = None
    created_at: Optional[ApiDateTime] = None
    updated_at: Optional[ApiDateTime] = None
    last_used_at: Optional[ApiDateTime] = None


class OpenApiAccessKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    permissions: list[OpenApiPermission] = Field(..., min_length=1)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Key 名称不能为空")
        return value


class OpenApiAccessKeyUpdate(OpenApiAccessKeyCreate):
    pass


class OpenApiAccessKeyCreatedOut(OpenApiAccessKeyOut):
    """创建或轮换后的 OpenAPI Key。"""


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
    enable_thinking: Optional[bool] = None
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
    enable_thinking: Optional[bool] = None
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
    enable_thinking: Optional[bool] = None
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
    trigger_type: Literal["manual", "scheduled", "open_api"] = "manual"
    benchmark_id: Optional[int] = None
    scheduled_evaluation_id: Optional[int] = None
    adapter_type: str
    total: int
    passed: int
    pass_rate: float
    medical_safety_failed: int
    n_runs: int
    # 已完成评测的用例总分均值（满分 45）；运行中 / 历史无评分数据时为 null。
    avg_composite: Optional[float] = None
    started_at: Optional[ApiDateTime] = None
    finished_at: Optional[ApiDateTime] = None
    created_at: Optional[ApiDateTime] = None
    created_by: Optional[str] = None
    error_msg: str = ""
    # 是否已落会话留痕（可离线重判/断点续跑）、是否置顶保护、重判/续跑的源 run
    has_traces: bool = False
    pinned: bool = False
    parent_run_id: Optional[int] = None
    evaluation_mode: Literal["single_turn", "multi_turn"] = "single_turn"


class RunDetailOut(RunSummaryOut):
    description: str = ""
    judge_overrides: dict[str, Any] = Field(default_factory=dict)
    adapter_overrides: dict[str, Any] = Field(default_factory=dict)
    grading: dict[str, Any] = Field(default_factory=dict)
    stability_distribution: dict[str, Any] = Field(default_factory=dict)
    latency_summary: dict[str, Any] = Field(default_factory=dict)
    ttft_summary: dict[str, Any] = Field(default_factory=dict)
    token_summary: dict[str, Any] = Field(default_factory=dict)
    pass_rate_ci: dict[str, Any] = Field(default_factory=dict)
    guideline_match: dict[str, Any] = Field(default_factory=dict)
    failure_tag_counter: dict[str, Any] = Field(default_factory=dict)
    judge_fingerprints: dict[str, Any] = Field(default_factory=dict)
    by_level: dict[str, Any] = Field(default_factory=dict)
    by_scenario: dict[str, Any] = Field(default_factory=dict)
    by_case_type: dict[str, Any] = Field(default_factory=dict)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)

    @field_validator("config_snapshot", mode="before")
    @classmethod
    def _redact_config_snapshot(cls, value: Any) -> dict[str, Any]:
        from medeval.config import redact_config_secrets

        return redact_config_secrets(value or {})


class ProgressOut(BaseModel):
    status: str
    progress: Optional[dict[str, Any]] = None
    queue_position: Optional[int] = None
    account_queue: dict[str, Any] = Field(default_factory=dict)


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
    case_type: str = ""
    sub_scenario: str
    level: str
    medical_safety_passed: bool
    release_passed: bool
    # 判分模型调用异常时为 True；前端据此展示“判分异常”，而非误判为 0 分不合格。
    judge_error: bool = False
    composite_score: Optional[float] = None
    grade: str
    stability: str
    guideline_earned: Optional[float] = None
    guideline_max: Optional[float] = None
    latency_ms: Optional[float] = None
    ttft_ms: Optional[float] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = None
    n_turns: int = 1
    # hit/miss/failed/triggered/not_triggered/unknown；以 Langfuse 工具链为准。
    rag_status: str = "unknown"
    failure_tags: list[str]
    review: Optional[ReviewSummary] = None
    # 该用例代表 trace 的 Langfuse 深链（追踪关闭/未配置/旧 run 时为 None）。仅用于前端跳转。
    langfuse_trace_url: Optional[str] = None


class CaseRetryRequest(BaseModel):
    """在原评测记录中重新执行所选用例。"""

    sample_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("sample_ids")
    @classmethod
    def _unique_sample_ids(cls, values: list[str]) -> list[str]:
        result = list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
        if not result:
            raise ValueError("请至少选择一个用例")
        return result


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
    reasons: list[str] = Field(default_factory=list)
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
    scope: Literal["all", "divergent_only", "rag_triggered_only"] = "all"
    note: str = ""


class PairwiseNoteUpdate(BaseModel):
    """二次编辑对比备注：仅改 note。"""

    note: str = ""


class PairwiseComparabilityOut(BaseModel):
    """可比性校验结果：comparable=False 时 reasons 给中文原因。"""

    comparable: bool
    reasons: list[str] = Field(default_factory=list)
    subject_diff: dict[str, Any] = Field(default_factory=dict)
    rag_analysis: dict[str, Any] = Field(default_factory=dict)


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
    """人工校准覆写：结论 A|B|tie、八维度、理由。"""

    winner: Literal["A", "B", "tie"]
    dimension_winners: dict[str, Literal["A", "B", "tie"]] = Field(default_factory=dict)
    reason: str = ""

    @field_validator("dimension_winners")
    @classmethod
    def _only_eight_dimensions(
        cls, value: dict[str, Literal["A", "B", "tie"]]
    ) -> dict[str, Literal["A", "B", "tie"]]:
        allowed = {dimension.value for dimension in EvaluationDimension}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"未知维度：{', '.join(unknown)}")
        return value


class PairwiseCaseVerdictOut(BaseModel):
    """有效值对外展示；机器原判仅在 human_calibrated 时回显 auto_*。"""

    sample_id: str
    scenario: str = ""
    sub_scenario: str = ""
    rag_status_a: str = "unknown"
    rag_status_b: str = "unknown"
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
    confidence: str = "low"


class PairwiseRunObservabilityOut(BaseModel):
    """Pairwise 两侧 Run 的性能与 token 聚合；仅观测，不参与胜负判定。"""

    latency_summary: dict[str, Any] = Field(default_factory=dict)
    ttft_summary: dict[str, Any] = Field(default_factory=dict)
    token_summary: dict[str, Any] = Field(default_factory=dict)


class PairwiseDetailOut(PairwiseComparisonOut):
    """对比结果详情：汇总 + 逐用例列表。"""

    verdicts: list[PairwiseCaseVerdictOut] = Field(default_factory=list)
    run_a_observability: PairwiseRunObservabilityOut = Field(
        default_factory=PairwiseRunObservabilityOut
    )
    run_b_observability: PairwiseRunObservabilityOut = Field(
        default_factory=PairwiseRunObservabilityOut
    )
