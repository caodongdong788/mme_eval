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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Benchmark(Base):
    """一个可复用的评测用例集（内置 builtin 或用户上传）。"""

    __tablename__ = "benchmark"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(50), default="v1")
    # builtin（指向仓库 cases/） | uploaded（存 uploads/benchmarks/<id>/）
    source: Mapped[str] = mapped_column(String(20), default="uploaded", index=True)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 该 benchmark 用例覆盖的 level 列表（如 ["L1","L3"]），用于库列表展示与筛选。
    levels: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 用例所在路径（相对 project_root）。builtin 指向 cases/xxx；uploaded 指向 uploads/...
    storage_path: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    runs: Mapped[list["EvalRun"]] = relationship(back_populates="benchmark")


class EvalRun(Base):
    """一次评测的 run 级汇总。"""

    __tablename__ = "eval_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_slug: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    # pending | running | success | failed
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error_msg: Mapped[str] = mapped_column(Text, default="")

    benchmark_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("benchmark.id"), nullable=True, index=True
    )
    benchmark: Mapped[Optional["Benchmark"]] = relationship(back_populates="runs")

    adapter_type: Mapped[str] = mapped_column(String(50), default="")
    # 评测打分模型覆盖（provider/model/base_url/...，不含明文 api_key）
    judge_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 被测 bot 可选覆盖（model/base_url/system_prompt 等，不含明文 api_key）
    adapter_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # 是否已落盘会话留痕（outputs/<slug>/traces.jsonl.gz 存在）→ 可离线重判 / 断点续跑
    has_traces: Mapped[bool] = mapped_column(Boolean, default=False)
    # 置顶保护：免于存储治理清理（同步落 KEEP 哨兵文件）
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # 重判 / 续跑产出的 run 指向其源 run（审计血缘）
    parent_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 汇总标量（来自 RunReport）
    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    hard_gate_failed: Mapped[int] = mapped_column(Integer, default=0)
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
    # 成本/Token 聚合（来自 RunReport.token_summary）。仅观测、不否决。
    token_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 通过率 bootstrap 置信区间（来自 RunReport.pass_rate_ci）。仅度量、不否决。
    pass_rate_ci: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    guideline_match: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    failure_tag_counter: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    judge_fingerprints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    by_level: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    by_scenario: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    case_results: Mapped[list["CaseResultRow"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


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
    sub_scenario: Mapped[str] = mapped_column(String(200), default="")
    level: Mapped[str] = mapped_column(String(20), default="", index=True)
    source: Mapped[str] = mapped_column(String(40), default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    hard_gate_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    release_passed: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    composite_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grade: Mapped[str] = mapped_column(String(20), default="")
    score_profile: Mapped[str] = mapped_column(String(40), default="", index=True)
    soft_score: Mapped[float] = mapped_column(Float, default=0.0)
    soft_score_max: Mapped[float] = mapped_column(Float, default=0.0)
    stability: Mapped[str] = mapped_column(String(20), default="stable_pass", index=True)
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    guideline_match_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 成本/Token 观测（仅观测、不否决）：该用例总 token 与折算成本。
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    failure_tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    # 完整 CaseResult.model_dump(mode="json")：对话、verdicts、扣分原因、命中关键词、得分点等
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


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


class ReleaseThresholdConfig(Base):
    """按评分档（profile）覆盖「综合分上线阈值」的全局配置：仅作用于之后发起的新评测。

    无行 = 该 profile 沿用 config.yaml 原 pass_rule（零行为变化）。只覆盖综合分阈值，
    不削弱 HardGate 与该 profile 原有的安全/合规 gates。
    """

    __tablename__ = "release_threshold_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    composite_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


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
