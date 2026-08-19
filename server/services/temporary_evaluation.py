"""OpenAPI 临时单轮评测内核：复用正式八维与指南判分，不创建正式 EvalRun。"""

from __future__ import annotations

import json
import re
from typing import Any
import unicodedata
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from medeval.evaluation import (
    DIMENSION_LABELS,
    DIMENSION_ROLES,
    ROLE_LABELS,
    EvaluationDimension,
)
from medeval.judges.aggregator import judge_all
from medeval.judges.llm_backend import configure_llm_rate_limit, reset_llm_rate_limit
from medeval.models import (
    CaseEvaluation,
    CaseInitialState,
    CaseResult,
    ChatMessage,
    ConversationTrace,
    Level,
    Source,
    TestCase,
    Turn,
)
from medeval.reporter.scoring import apply_grading

from .. import benchmarks as bm_domain
from ..models_db import Benchmark, JudgeModelConfig
from ..schemas import (
    JudgeOverride,
    OpenTemporaryCaseSource,
    OpenTemporaryDimensionResult,
    OpenTemporaryEvaluationCreate,
    OpenTemporaryEvaluationOut,
    OpenTemporaryGuidelineResult,
)
from ..settings import get_settings
from . import judge_models as judge_models_svc
from .eval_stack import build_judge_stack, prepare_run_config


def _judge_override(
    session: Session,
    judge_model_id: int | None,
) -> tuple[dict[str, Any], int | None, str | None]:
    if judge_model_id is None:
        return {"enabled": True}, None, None

    model = session.get(JudgeModelConfig, judge_model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"判分模型 {judge_model_id} 不存在")
    if not judge_models_svc.has_judge_model_api_key(model):
        raise HTTPException(
            status_code=422,
            detail=f"判分模型「{model.name}」未配置可用的 API Key",
        )
    override = JudgeOverride(
        enabled=True,
        provider=model.provider or None,
        model=model.model or None,
        base_url=model.base_url or None,
        api_version=model.api_version or None,
        api_key=model.api_key or None,
        temperature=model.temperature,
        enable_thinking=model.enable_thinking,
    )
    return override.model_dump(exclude_none=True), model.id, model.name


def _temporary_context(payload: OpenTemporaryEvaluationCreate) -> CaseInitialState:
    """把外部证据放入 Judge 已支持的 initial_state，且与用户画像明确隔离。"""
    auxiliary_context = {
        "说明": "以下内容是本次回答生成时可用的已知上下文，判分时可作为事实与个性化依据。",
        "RAG引用": [item.model_dump(mode="json") for item in payload.rag_references],
        "病例夹": [item.model_dump(mode="json") for item in payload.saved_contents],
    }
    user_profile = {
        "用户画像": payload.user_profile,
        "临时评测辅助上下文": auxiliary_context,
    }
    timeline = [item.model_dump(mode="json") for item in payload.past_facts]
    return CaseInitialState(user_profile=user_profile, timeline=timeline)


def _normalize_question(value: str) -> str:
    """只消除排版差异，避免用模糊语义把相似问题误认成同一个 Case。"""
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", "", normalized).strip()


def _case_opening_question(case: TestCase) -> str:
    if case.conversation is not None:
        return case.conversation.opening.content
    return next((turn.content for turn in case.turns if turn.role == "user"), "")


def _is_single_turn_case(case: TestCase) -> bool:
    return (
        case.conversation is None
        and sum(turn.role == "user" for turn in case.turns) == 1
    )


def _evaluation_contract_key(case: TestCase) -> str:
    """断言不属于临时评测契约；仅比较八维补充评分点和指南检查点。"""
    contract = case.evaluation.model_dump(mode="json", exclude={"assertions"})
    return json.dumps(
        contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _platform_benchmarks(session: Session) -> list[Benchmark]:
    benchmarks = list(session.scalars(select(Benchmark).order_by(Benchmark.id)))
    if not any(benchmark.source == "builtin" for benchmark in benchmarks):
        bm_domain.ensure_builtin_benchmark(session)
        benchmarks = list(session.scalars(select(Benchmark).order_by(Benchmark.id)))
    return benchmarks


def _match_platform_case(
    session: Session,
    question: str,
) -> tuple[Benchmark, TestCase] | None:
    """在全部已注册 Benchmark 中按标准化后的开场问题做确定性精确匹配。"""
    target = _normalize_question(question)
    matches: list[tuple[Benchmark, TestCase]] = []
    unsupported_multi_turn_matches: list[tuple[Benchmark, TestCase]] = []
    for benchmark in _platform_benchmarks(session):
        # 历史测试/占位记录可能没有实际 Case 存储；空路径不能交给 loader，
        # 否则会被解析成项目根目录并误扫其他 YAML。
        if not str(benchmark.storage_path or "").strip():
            continue
        try:
            cases = bm_domain.load_benchmark_cases(benchmark)
        except Exception as exc:  # noqa: BLE001 - 不能静默漏掉可能含目标 Case 的用例集
            raise HTTPException(
                status_code=503,
                detail=(
                    f"平台 Benchmark Case 索引暂不可用：benchmark {benchmark.id} 加载失败"
                ),
            ) from exc
        if int(benchmark.case_count or 0) > 0 and not cases:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"平台 Benchmark Case 索引暂不可用：benchmark {benchmark.id} 没有加载到 Case"
                ),
            )
        for case in cases:
            if _normalize_question(_case_opening_question(case)) != target:
                continue
            target_collection = (
                matches if _is_single_turn_case(case) else unsupported_multi_turn_matches
            )
            target_collection.append((benchmark, case))

    if not matches:
        if unsupported_multi_turn_matches:
            candidates = "、".join(
                f"{benchmark.id}/{case.sample_id}"
                for benchmark, case in unsupported_multi_turn_matches
            )
            raise HTTPException(
                status_code=422,
                detail=(
                    "问题命中了多轮平台 Case，临时评测目前仅支持单轮模式："
                    f"{candidates}"
                ),
            )
        return None

    contract_groups: dict[str, list[tuple[Benchmark, TestCase]]] = {}
    for match in matches:
        contract_groups.setdefault(_evaluation_contract_key(match[1]), []).append(match)
    if len(contract_groups) > 1:
        candidates = "、".join(
            f"{benchmark.id}/{case.sample_id}" for benchmark, case in matches
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "同一问题命中了评分契约不同的平台 Case："
                f"{candidates}。请先统一重复 Case 的评分点和指南检查点"
            ),
        )

    return min(matches, key=lambda item: (item[0].id, item[1].sample_id))


def _temporary_case(
    session: Session,
    payload: OpenTemporaryEvaluationCreate,
    evaluation_id: str,
) -> tuple[TestCase, OpenTemporaryCaseSource | None]:
    evaluation = CaseEvaluation()
    scenario = "OpenAPI 临时单轮评测"
    level = Level.L2
    case_type = "临时评测"
    case_source: OpenTemporaryCaseSource | None = None

    matched = _match_platform_case(session, payload.question)
    if matched is not None:
        benchmark, selected = matched
        # 临时评测只继承评分契约。原 Case 的问答、画像、断言和运行证据均不混入本次请求。
        evaluation = CaseEvaluation(
            dimension_criteria=selected.evaluation.dimension_criteria,
            guidelines=selected.evaluation.guidelines,
        ).model_copy(deep=True)
        scenario = selected.scenario
        level = selected.level
        case_type = selected.case_type
        case_source = OpenTemporaryCaseSource(
            benchmark_id=benchmark.id,
            benchmark_name=benchmark.name,
            sample_id=selected.sample_id,
            scenario=selected.scenario,
        )

    case = TestCase(
        schema_version="2.1",
        sample_id=evaluation_id,
        scenario=scenario,
        level=level,
        source=Source.offline,
        case_type=case_type,
        initial_state=_temporary_context(payload),
        turns=[Turn(role="user", content=payload.question)],
        evaluation=evaluation,
        notes="OpenAPI 临时评测；输入与结果仅进入七天临时存储，不创建正式 EvalRun。",
    )
    return case, case_source


def _dimension_results(result: CaseResult) -> list[OpenTemporaryDimensionResult]:
    by_name = {verdict.name: verdict for verdict in result.verdicts}
    rows: list[OpenTemporaryDimensionResult] = []
    for dimension in EvaluationDimension:
        verdict = by_name[f"dimension.{dimension.value}"]
        raw_score = max(0.0, min(5.0, float(verdict.score)))
        if dimension == EvaluationDimension.medical_safety and raw_score != 5.0:
            raw_score = 0.0
        final_score = float(result.dimension_scores.get(dimension.value, 0.0))
        details = verdict.details or {}
        role = DIMENSION_ROLES[dimension]
        rows.append(
            OpenTemporaryDimensionResult(
                dimension=dimension,
                label=DIMENSION_LABELS[dimension],
                role=role,
                role_label=ROLE_LABELS[role],
                raw_score=raw_score,
                score=final_score,
                base_deduction=max(0.0, 5.0 - raw_score),
                guideline_deduction=max(0.0, raw_score - final_score),
                deduction=max(0.0, 5.0 - final_score),
                reason=verdict.reason,
                evidence=list(verdict.evidence),
                satisfied_points=list(details.get("satisfied_points", [])),
                issue_audits=list(details.get("issue_audits", [])),
            )
        )
    return rows


def _guideline_results(result: CaseResult) -> list[OpenTemporaryGuidelineResult]:
    rows: list[OpenTemporaryGuidelineResult] = []
    for item in result.guideline_scores:
        dimension = EvaluationDimension(str(item["dimension"]))
        rows.append(
            OpenTemporaryGuidelineResult(
                id=str(item["id"]),
                dimension=dimension,
                dimension_label=DIMENSION_LABELS[dimension],
                trigger=str(item.get("trigger", "")),
                checkpoints=list(item.get("checkpoints", [])),
                applicable=bool(item.get("applicable", True)),
                score=float(item.get("score", 0.0)),
                max_score=float(item.get("max_score", 0.0)),
                deduction=float(item.get("deduction", 0.0)),
                reason=str(item.get("reason", "")),
                evidence=list(item.get("evidence", [])),
                missed_points=list(item.get("missed_points", [])),
                checkpoint_audits=list(item.get("checkpoint_audits", [])),
            )
        )
    return rows


def _deduction_summary(
    dimensions: list[OpenTemporaryDimensionResult],
    score_deductions: list[str],
) -> list[str]:
    dimension_deductions = [
        f"{item.label} -{item.base_deduction:g}分：{item.reason or '未完全满足该维度要求'}"
        for item in dimensions
        if item.base_deduction > 0
    ]
    return list(dict.fromkeys([*dimension_deductions, *score_deductions]))


async def evaluate_temporary_conversation(
    session: Session,
    payload: OpenTemporaryEvaluationCreate,
    *,
    evaluation_id: str | None = None,
    case_snapshot: TestCase | None = None,
    case_source_snapshot: OpenTemporaryCaseSource | None = None,
) -> OpenTemporaryEvaluationOut:
    """执行一次判分；任务持久化与租约状态由上层临时任务服务负责。"""
    evaluation_id = evaluation_id or f"temporary_{uuid4().hex}"
    judge_override, judge_model_id, judge_model_name = _judge_override(
        session, payload.judge_model_id
    )
    if case_snapshot is None:
        case, case_source = _temporary_case(session, payload, evaluation_id)
    else:
        case = case_snapshot
        case_source = case_source_snapshot
    config = prepare_run_config(
        get_settings(),
        run_name=evaluation_id,
        repeat=1,
        judge_ov=judge_override,
    )
    judge_model_name = judge_model_name or config.judges.eight_dimension.model
    trace = ConversationTrace(
        messages=[
            ChatMessage(role="user", content=payload.question),
            ChatMessage(role="assistant", content=payload.answer),
        ]
    )
    configure_llm_rate_limit(
        config.run.judge_concurrency,
        config.run.llm_min_interval_s,
    )
    try:
        result = await judge_all(case, trace, build_judge_stack(config))
    finally:
        reset_llm_rate_limit()
    apply_grading([result])

    verdict_names = {verdict.name for verdict in result.verdicts}
    missing_dimensions = [
        dimension.value
        for dimension in EvaluationDimension
        if f"dimension.{dimension.value}" not in verdict_names
    ]
    missing_guidelines = [
        guideline.id
        for guideline in case.evaluation.guidelines
        if f"guideline.{guideline.id}" not in verdict_names
    ]
    if result.judge_error or missing_dimensions or missing_guidelines:
        missing = ", ".join([*missing_dimensions, *missing_guidelines])
        detail = "临时评测判分失败，请检查判分模型配置或稍后重试"
        if missing:
            detail += f"（缺少判分结果：{missing}）"
        raise HTTPException(status_code=502, detail=detail)

    dimensions = _dimension_results(result)
    return OpenTemporaryEvaluationOut(
        evaluation_id=evaluation_id,
        external_request_id=payload.external_request_id,
        evaluation_mode="single_turn",
        judge_model_id=judge_model_id,
        judge_model_name=judge_model_name,
        benchmark_case_matched=case_source is not None,
        case_source=case_source,
        total_score=float(result.composite_score or 0.0),
        grade=result.grade,
        passed=result.release_passed,
        medical_safety_passed=result.medical_safety_passed,
        end_scores=result.end_scores,
        dimensions=dimensions,
        guideline_results=_guideline_results(result),
        deductions=_deduction_summary(dimensions, result.score_deductions),
    )
