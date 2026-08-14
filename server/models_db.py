"""平台 ORM 表：benchmark / eval_run / case_result。

设计：看板聚合走规范化标量列；单条用例完整明细存 ``case_result.detail_json``（JSON 列），
避免列表查询拉取大字段。预留 ``created_by`` 供未来多用户。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

_EVALUATION_MODE_TAG_PREFIX = "__mme_evaluation_mode:"
_EVALUATION_MODES = {"single_turn", "multi_turn"}
_SUITE_TYPE_TAG_PREFIX = "__mme_suite_type:"
_SUITE_TYPES = {"capability", "regression"}


class Benchmark(Base):
    """一个可复用的评测用例集（内置 builtin 或用户上传）。"""

    __tablename__ = "benchmark"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(50), default="v1")
    # builtin（指向仓库 cases/） | online（线上真实流量） | offline（线下构造/上传）
    source: Mapped[str] = mapped_column(String(20), default="offline", index=True)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 该 benchmark 用例覆盖的 level 列表（如 ["L1","L3"]），用于库列表展示与筛选。
    levels: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 用例所在路径（相对 project_root）。builtin 指向 cases/xxx；uploaded 指向 uploads/...
    storage_path: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    runs: Mapped[list["EvalRun"]] = relationship(back_populates="benchmark")

    def mark_updated(self) -> None:
        """记录用例集内容或人工维护发生变化。"""
        self.updated_at = datetime.utcnow()

    @property
    def default_evaluation_mode(self) -> str:
        """Benchmark 推荐的发起模式，复用 tags 持久化以免新增生产库迁移。"""
        for tag in self.tags or []:
            if isinstance(tag, str) and tag.startswith(_EVALUATION_MODE_TAG_PREFIX):
                mode = tag.removeprefix(_EVALUATION_MODE_TAG_PREFIX)
                if mode in _EVALUATION_MODES:
                    return mode
        return "single_turn"

    @default_evaluation_mode.setter
    def default_evaluation_mode(self, mode: str) -> None:
        if mode not in _EVALUATION_MODES:
            raise ValueError("default_evaluation_mode 必须是 single_turn 或 multi_turn")
        tags = [
            tag
            for tag in (self.tags or [])
            if not (isinstance(tag, str) and tag.startswith(_EVALUATION_MODE_TAG_PREFIX))
        ]
        tags.append(f"{_EVALUATION_MODE_TAG_PREFIX}{mode}")
        self.tags = tags

    @property
    def suite_type(self) -> str:
        """能力集用于探索，回归集用于发布门禁；同样通过 tags 兼容已有生产库。"""
        for tag in self.tags or []:
            if isinstance(tag, str) and tag.startswith(_SUITE_TYPE_TAG_PREFIX):
                value = tag.removeprefix(_SUITE_TYPE_TAG_PREFIX)
                if value in _SUITE_TYPES:
                    return value
        return "capability"

    @suite_type.setter
    def suite_type(self, value: str) -> None:
        if value not in _SUITE_TYPES:
            raise ValueError("suite_type 必须是 capability 或 regression")
        self.tags = [tag for tag in (self.tags or []) if not (
            isinstance(tag, str) and tag.startswith(_SUITE_TYPE_TAG_PREFIX)
        )] + [f"{_SUITE_TYPE_TAG_PREFIX}{value}"]


class EvalRun(Base):
    """一次评测的 run 级汇总。"""

    __tablename__ = "eval_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_slug: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    # pending | running | success | failed
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # manual（页面发起） | scheduled（定时任务） | open_api（开放接口）。
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual", index=True)
    error_msg: Mapped[str] = mapped_column(Text, default="")

    benchmark_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("benchmark.id"), nullable=True, index=True
    )
    benchmark: Mapped[Optional["Benchmark"]] = relationship(back_populates="runs")
    # 定时任务触发的 run 记录其来源任务，供回归趋势按任务连续分析。
    scheduled_evaluation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("scheduled_evaluation.id"), nullable=True, index=True
    )

    adapter_type: Mapped[str] = mapped_column(String(50), default="")
    # 评测打分模型覆盖（provider/model/base_url/...，不含明文 api_key）
    judge_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 被测 bot 可选覆盖（model/base_url/system_prompt 等，不含明文 api_key）
    adapter_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    @property
    def evaluation_mode(self) -> str:
        """兼容旧 Run：未记录模式的历史数据一律按 main 固定 turns 语义展示。"""
        mode = (self.adapter_overrides or {}).get("evaluation_mode")
        return mode if mode in {"single_turn", "multi_turn"} else "single_turn"

    # 是否已落盘会话留痕（outputs/<slug>/traces.jsonl.gz 存在）→ 可离线重判 / 断点续跑
    has_traces: Mapped[bool] = mapped_column(Boolean, default=False)
    # 置顶保护：免于存储治理清理（同步落 KEEP 哨兵文件）
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # 重判 / 续跑产出的 run 指向其源 run（审计血缘）
    parent_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 版本对比基线 run（outputs resolve_diff_target 落库时写入）
    diff_against_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 汇总标量（来自 RunReport）
    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    medical_safety_failed: Mapped[int] = mapped_column(Integer, default=0)
    n_runs: Mapped[int] = mapped_column(Integer, default=1)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 进度（running 时由 JobRunner 写入）：{phase, label, done, total}
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # 聚合/明细 JSON（来自 RunReport 的同名字段）
    grading: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    stability_distribution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    latency_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 流式首 Token 耗时聚合；历史/非流式 Run 为空。
    ttft_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 成本/Token 聚合（来自 RunReport.token_summary）。仅观测、不否决。
    token_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 通过率 bootstrap 置信区间（来自 RunReport.pass_rate_ci）。仅度量、不否决。
    pass_rate_ci: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    guideline_match: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    failure_tag_counter: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    judge_fingerprints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    by_level: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    by_scenario: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    by_case_type: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    case_results: Mapped[list["CaseResultRow"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    evaluation_jobs: Mapped[list["EvaluationJob"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class EvaluationJob(Base):
    """可由独立 Worker 领取、续租和恢复的持久化评测任务。"""

    __tablename__ = "evaluation_job"
    __table_args__ = (
        Index("ix_evaluation_job_claim", "status", "lease_expires_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("eval_run.id", ondelete="CASCADE"), index=True, nullable=False
    )
    run: Mapped["EvalRun"] = relationship(back_populates="evaluation_jobs")
    # evaluation | resume | rejudge | cases_retry
    kind: Mapped[str] = mapped_column(String(40), index=True)
    # 仅保存可公开/可重建的参数；API Key 通过环境变量或模型配置表在 Worker 内解析。
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # queued | running | succeeded | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(160), nullable=True, index=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ScheduledEvaluation(Base):
    """用户配置的周期性评测任务。

    任务本身只保存运行参数；每次触发都会创建一个独立 EvalRun，便于审计和看板追溯。
    """

    __tablename__ = "scheduled_evaluation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    benchmark_id: Mapped[int] = mapped_column(ForeignKey("benchmark.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # daily | weekly；weekly 使用 weekdays（0=周一，6=周日）。
    schedule_kind: Mapped[str] = mapped_column(String(20), default="daily")
    schedule_time: Mapped[str] = mapped_column(String(5), default="09:00")
    weekdays: Mapped[list[int]] = mapped_column(JSON, default=list)

    evaluation_mode: Mapped[str] = mapped_column(String(20), default="single_turn")
    levels: Mapped[list[str]] = mapped_column(JSON, default=list)
    limit: Mapped[int] = mapped_column(Integer, default=0)
    repeat: Mapped[int] = mapped_column(Integer, default=1)
    enable_rag: Mapped[bool] = mapped_column(Boolean, default=False)
    enable_judge: Mapped[bool] = mapped_column(Boolean, default=True)
    judge_model_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    user_simulator_model_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class CaseResultRow(Base):
    """单条用例结果：可筛选标量列 + 完整明细 detail_json。"""

    __tablename__ = "case_result"
    # 高频访问模式：按 run_id 过滤 + sample_id 排序 / 按 (run_id, release_passed) 统计。
    __table_args__ = (
        Index("ix_case_result_run_sample", "run_id", "sample_id"),
        Index("ix_case_result_run_release", "run_id", "release_passed"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("eval_run.id"), index=True, nullable=False
    )
    run: Mapped["EvalRun"] = relationship(back_populates="case_results")

    sample_id: Mapped[str] = mapped_column(String(200), index=True)
    scenario: Mapped[str] = mapped_column(String(200), default="", index=True)
    # YAML 中的用例类别；与 scenario 分开持久化，供列表直接展示/筛选。
    case_type: Mapped[str] = mapped_column(String(200), default="")
    sub_scenario: Mapped[str] = mapped_column(String(200), default="")
    level: Mapped[str] = mapped_column(String(20), default="", index=True)
    source: Mapped[str] = mapped_column(String(40), default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    medical_safety_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    release_passed: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    judge_error: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    composite_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    guideline_earned: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    guideline_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grade: Mapped[str] = mapped_column(String(20), default="")
    stability: Mapped[str] = mapped_column(String(20), default="stable_pass", index=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 代表性会话各成功回复轮次 TTFT 的平均值；历史/非流式数据为空。
    ttft_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 成本/Token 观测（仅观测、不否决）：该用例总 token 与折算成本。
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 列表页高频展示字段。它们从 detail_json 派生，但单独持久化，避免 100 条用例
    # 列表每次都解析对话/调用链的大 JSON。
    n_turns: Mapped[int] = mapped_column(Integer, default=1)
    rag_status: Mapped[str] = mapped_column(String(20), default="unknown")
    failure_tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    # 完整 CaseResult：对话、八维原始/最终分、指南得分和扣分原因。
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AttributionTask(Base):
    """一批不合格用例的 AI 归因任务。

    任务和逐 Case 结果分表保存，页面可以轮询到已完成项，不需要等待整批 LLM 调用结束。
    """

    __tablename__ = "attribution_task"
    __table_args__ = (
        Index(
            "uq_attribution_task_active_run",
            "run_id",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("eval_run.id"), index=True, nullable=False)
    judge_model_id: Mapped[int] = mapped_column(Integer, nullable=False)
    judge_model_name: Mapped[str] = mapped_column(String(200), default="")
    # queued | running | success | partial | failed
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    requested_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AttributionTaskItem(Base):
    """批量归因任务中的单条 Case 执行状态。"""

    __tablename__ = "attribution_task_item"
    __table_args__ = (
        UniqueConstraint("task_id", "sample_id", name="uq_attribution_task_item_sample"),
        Index("ix_attribution_task_item_task_status", "task_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("attribution_task.id"), index=True, nullable=False)
    sample_id: Mapped[str] = mapped_column(String(200), index=True)
    # pending | running | success | failed
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # 在同一归因任务内手动重跑该 Case 的次数；首次归因保持 0。
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    # 每次任务独立保存本次模型返回，避免后续重新归因覆盖旧任务的查看结果。
    analysis_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PairwiseComparison(Base):
    """一次 Pairwise 对比：同一裁判模型对两个 run 逐题 PK 的 run 级记录。

    产出**相对偏好**（不进任何 gate）。可比性「只卡判分尺子、放开被测 bot」由发起时校验。
    参见 OpenSpec change add-pairwise-comparison。
    """

    __tablename__ = "pairwise_comparison"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # A=基线，B=本次（与 PairwiseResult 的 A/B 语义一致）。
    run_a_id: Mapped[int] = mapped_column(
        ForeignKey("eval_run.id"), index=True, nullable=False
    )
    run_b_id: Mapped[int] = mapped_column(
        ForeignKey("eval_run.id"), index=True, nullable=False
    )
    judge_model: Mapped[str] = mapped_column(String(200), default="")
    judge_fingerprint: Mapped[str] = mapped_column(String(40), default="")
    # 自由文本备注：本次对比目的，可二次编辑（不影响判分/汇总/可比性）。
    note: Mapped[str] = mapped_column(Text, default="")
    # running | done | failed
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    scope: Mapped[str] = mapped_column(String(20), default="all")
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    done_cases: Mapped[int] = mapped_column(Integer, default=0)
    # 被测差异（system_prompt / 被测 model 等，不拦截只展示）。
    subject_diff: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 汇总：胜/平/负、低置信、按维度胜率、回退用例清单。
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    verdicts: Mapped[list["PairwiseCaseVerdict"]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan"
    )


class PairwiseCaseVerdict(Base):
    """一道用例的相对偏好结论（A 基线 vs B 本次）。"""

    __tablename__ = "pairwise_case_verdict"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comparison_id: Mapped[int] = mapped_column(
        ForeignKey("pairwise_comparison.id"), index=True, nullable=False
    )
    comparison: Mapped["PairwiseComparison"] = relationship(back_populates="verdicts")

    sample_id: Mapped[str] = mapped_column(String(200), index=True)
    # 用例场景描述（冗余存一份，列表/明细直接展示，免再查 detail_json）。
    scenario: Mapped[str] = mapped_column(Text, default="")
    # 细分场景（比 scenario 更具体，列表用例列优先展示）。
    sub_scenario: Mapped[str] = mapped_column(Text, default="")
    winner: Mapped[str] = mapped_column(String(8), default="tie")  # A | B | tie
    confidence: Mapped[str] = mapped_column(String(8), default="low")  # high | low
    swap_consistent: Mapped[bool] = mapped_column(Boolean, default=False)
    dimension_winners: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")
    # 两次 pass 留痕：[{"top": "A|B", "winner": "A|B|tie", "reason": <已翻译>}]，
    # 供顺序敏感用例如实并列两次分歧（不影响判定）。
    order_runs: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # 人工校准覆写（有效值优先；机器原判字段保留不重写）。
    human_calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    human_winner: Mapped[str] = mapped_column(String(8), default="")
    human_dimension_winners: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    human_reason: Mapped[str] = mapped_column(Text, default="")
    human_calibrated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    human_calibrated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class CaseAnnotation(Base):
    """一条人工审核裁定（HITL）：旁路记录，永不回写判分字段。

    同一 (run_id, sample_id) 可有多条（多人留意见）；verdict ∈ {agree, override}。
    """

    __tablename__ = "case_annotation"
    # 审核摘要按 (run_id, sample_id) 聚合，复合索引覆盖。
    __table_args__ = (
        Index("ix_case_annotation_run_sample", "run_id", "sample_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("eval_run.id"), index=True, nullable=False
    )
    sample_id: Mapped[str] = mapped_column(String(200), index=True)
    reviewer: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    verdict: Mapped[str] = mapped_column(String(20))  # agree | override
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JudgeModelConfig(Base):
    """一条可复用的判分模型（LLM-as-Judge）配置：全局共享，发起评测时下拉选用。

    api_key 落库但只写不读——读取类接口只回 has_api_key 掩码，发起评测时服务端读取注入运行期。
    """

    __tablename__ = "judge_model_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), default="openai")
    model: Mapped[str] = mapped_column(String(120), default="")
    base_url: Mapped[str] = mapped_column(String(500), default="")
    api_version: Mapped[str] = mapped_column(String(60), default="")
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    enable_thinking: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # Pairwise 对比题间并发度（仅作用于对比，不影响主评测链路）。默认 4。
    pairwise_concurrency: Mapped[int] = mapped_column(Integer, default=4)
    # 只写不读：仅服务端发起评测时读取注入，接口侧只暴露 has_api_key。
    api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


class OpenApiAccessKey(Base):
    """一把可独立授权、可撤销的 OpenAPI 密钥。

    为满足管理员可随时复制的需求，明文只在平台登录后的参数配置接口中可读取；
    对外 OpenAPI 的鉴权始终只使用 ``key_hash``。
    """

    __tablename__ = "open_api_access_key"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # 仅参数配置页（需平台登录）可读取，用于管理员复制；OpenAPI 本身只按 key_hash 校验。
    api_key: Mapped[str] = mapped_column(Text, default="")
    key_prefix: Mapped[str] = mapped_column(String(32), default="")
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class FeishuUser(Base):
    """一个飞书登录用户及其 per-user OAuth token 缓存。

    token 缓存 + 自动刷新：access 临过期时用 refresh_token 续期，refresh 过期才要求重登。
    有效期均取飞书返回值，不硬编码。token 当前明文存（本地 SQLite），后续可加密加固。
    """

    __tablename__ = "feishu_user"

    open_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    avatar_url: Mapped[str] = mapped_column(Text, default="")

    access_token: Mapped[str] = mapped_column(Text, default="")
    access_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    refresh_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scope: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(Base):
    """服务端会话：浏览器只持随机 session_id（httpOnly cookie），token 不下发前端。"""

    __tablename__ = "user_session"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    open_id: Mapped[str] = mapped_column(
        ForeignKey("feishu_user.open_id"), index=True, nullable=False
    )
    user: Mapped["FeishuUser"] = relationship(back_populates="sessions")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
