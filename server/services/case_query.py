"""用例结果查询、派生展示字段与 HITL 队列辅助。"""

from __future__ import annotations

import json
from typing import Any, Optional

import yaml
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session, load_only

from ..models_db import CaseAnnotation, CaseResultRow
from ..schemas import CaseScores, ReviewSummary

_LIST_CASE_COLUMNS = tuple(
    getattr(CaseResultRow, attr.key)
    for attr in sa_inspect(CaseResultRow).column_attrs
    if attr.key != "detail_json"
)

# Pairwise 的“真实触发 RAG”只认 Agent 工具链证据。以下状态都表示至少发生过
# 一次医学文献工具调用；是否召回成功由具体状态继续区分。
RAG_TRIGGERED_STATUSES = frozenset({"hit", "miss", "failed", "triggered"})


def _json_fragment(value: Any) -> Any:
    """兼容 PostgreSQL JSONB 与 SQLite JSON 提取结果。"""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _count_user_turns(turns: Any) -> int:
    turns = _json_fragment(turns)
    if not isinstance(turns, list):
        return 1
    n = sum(1 for turn in turns if isinstance(turn, dict) and turn.get("role") == "user")
    return n or 1


def case_n_turns_from_detail(detail: Any) -> int:
    """从冻结 Case JSON 计算用户轮数（写入列表标量列及历史回填共用）。"""
    detail = detail if isinstance(detail, dict) else {}
    case = detail.get("case") if isinstance(detail.get("case"), dict) else {}
    turns = case.get("turns") if isinstance(case, dict) else None
    count = _count_user_turns(turns)
    if count > 1 or isinstance(turns, list):
        return count
    trace = detail.get("trace") if isinstance(detail.get("trace"), dict) else {}
    return _count_user_turns(trace.get("messages"))


def case_type_from_detail(detail: Any) -> str:
    """从冻结 Case YAML 快照提取类别，兼容早期使用 ``type`` 的数据。"""
    detail = detail if isinstance(detail, dict) else {}
    case = detail.get("case") if isinstance(detail.get("case"), dict) else {}
    value = case.get("case_type") or case.get("type")
    return str(value).strip() if value is not None else ""


def _rag_status_from_summary(summary: Any, chain_status: Any = None) -> str:
    summary = _json_fragment(summary)
    sources = summary.get("sources") if isinstance(summary, dict) else None
    if isinstance(sources, list):
        rag = next(
            (item for item in sources if isinstance(item, dict) and item.get("key") == "literature_rag"),
            None,
        )
        if rag is not None:
            calls = rag.get("calls")
            if isinstance(calls, (int, float)) and calls > 0:
                status = str(rag.get("status") or "").lower()
                if status in {"hit", "miss", "failed"}:
                    return status
                return "triggered"
            if chain_status in {"synced", "partial"}:
                return "not_triggered"
    return "unknown"


def _rag_status_from_audit_snapshots(trace: dict[str, Any]) -> str | None:
    """从 cx-agent 保存的医学文献审计快照推导 RAG 状态。

    Langfuse 的链路可能延迟写入或因体积被截断；审计快照来自 cx-agent 的
    文献工具调用结果，已经是更直接、且可在链路未同步时使用的证据。
    """
    audits = trace.get("cx_literature_audits")
    if not isinstance(audits, list):
        return None

    valid_audits = [item for item in audits if isinstance(item, dict)]
    if not valid_audits:
        if trace.get("cx_literature_audit_fetched") is True:
            return "not_triggered"
        # 兼容上线前已完成的 cx-agent Case：该版本没有显式成功标记，但有
        # cx session 且无审计错误时，空审计同样表示“未触发”，不应再展示为
        # Langfuse 链路未同步。
        identity = trace.get("evaluation_identity")
        if (
            isinstance(identity, dict)
            and isinstance(identity.get("cx_session_id"), str)
            and identity["cx_session_id"]
            and not trace.get("cx_literature_audit_error")
        ):
            return "not_triggered"
        return None

    selected_count = 0
    for audit in valid_audits:
        value = audit.get("selectedSourceCount", audit.get("selected_source_count", 0))
        try:
            selected_count += max(0, int(value or 0))
        except (TypeError, ValueError):
            continue
    return "hit" if selected_count > 0 else "miss"


def case_rag_status_from_detail(detail: Any) -> str:
    """从冻结链路快照提取真实 RAG 状态，供写入标量列和历史回填使用。"""
    detail = detail if isinstance(detail, dict) else {}
    trace = detail.get("trace") if isinstance(detail.get("trace"), dict) else {}

    # 审计快照优先于 Langfuse：它由 cx-agent 在同一次请求中保存，不受异步
    # 同步、采样和原始 trace 截断影响。
    audit_status = _rag_status_from_audit_snapshots(trace)
    if audit_status is not None:
        return audit_status

    chain = trace.get("agent_chain") if isinstance(trace.get("agent_chain"), dict) else {}
    if not chain:
        return "unknown"

    status = _rag_status_from_summary(chain.get("summary"), chain.get("status"))
    if status != "unknown":
        return status

    nodes = chain.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = str(node.get("name") or "").removeprefix("tool.")
            if name == "medical_literature_search":
                level = str(node.get("level") or "").upper()
                if level == "ERROR" or node.get("status_message"):
                    return "failed"
                return "triggered"
        if chain.get("status") in {"synced", "partial"}:
            return "not_triggered"
    return "unknown"


def case_ttft_ms_from_detail(detail: Any) -> float | None:
    """从 CaseResult JSON 取代表性会话的平均 TTFT，兼容历史空数据。"""
    detail = detail if isinstance(detail, dict) else {}
    trace = detail.get("trace") if isinstance(detail.get("trace"), dict) else {}
    raw_values = trace.get("turn_ttft_ms")
    if not isinstance(raw_values, list):
        return None
    values = [
        float(value)
        for value in raw_values
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
    ]
    return (sum(values) / len(values)) if values else None


def _attach_row_display_fields(
    row: CaseResultRow,
    *,
    load_detail_json: bool,
    turns: Any = None,
    chain_summary: Any = None,
    chain_status: Any = None,
    compact: bool = False,
) -> None:
    if load_detail_json:
        row.n_turns = _count_user_turns(turns) if compact else case_n_turns(row)
        row.langfuse_trace_url = None if compact else case_trace_url(row)
        row.rag_status = (
            _rag_status_from_summary(chain_summary, chain_status)
            if chain_summary is not None or chain_status is not None
            else case_rag_status(row)
        )
        # 入库时已持久化指南得分；列表不再为此读取整条 detail_json。
    else:
        row.n_turns = row.n_turns or 1
        row.langfuse_trace_url = None
        row.rag_status = row.rag_status or "unknown"


def case_n_turns(row: CaseResultRow) -> int:
    return case_n_turns_from_detail(row.detail_json)


def case_trace_url(row: CaseResultRow) -> Optional[str]:
    detail = row.detail_json or {}
    url = ((detail.get("trace") or {}).get("langfuse_trace_url"))
    return url if isinstance(url, str) and url else None


def case_rag_status(row: CaseResultRow) -> str:
    """返回医学文献 RAG 的真实调用状态，而非本次 Run 的开关状态。

    ``enable_rag`` 仅表示 Agent 可以使用 RAG；是否真的触发优先以 cx-agent
    保存的文献审计快照判断，缺失时再回退到 Langfuse 工具链证据。
    """
    return case_rag_status_from_detail(row.detail_json)


def guideline_counts(row: CaseResultRow) -> Optional[tuple[float, float]]:
    detail = row.detail_json or {}
    scores = detail.get("guideline_scores") or []
    applicable = [item for item in scores if item.get("applicable", True)]
    if not applicable:
        return None
    return (
        sum(float(item.get("score", 0)) for item in applicable),
        sum(float(item.get("max_score", 0)) for item in applicable),
    )


def _filtered_case_stmt(
    run_id: int,
    *,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    turns: Optional[str] = None,
    guideline: Optional[str] = None,
    load_detail_json: bool = True,
    load_full_detail_json: bool = False,
    sample_ids: set[str] | None = None,
):
    stmt = select(CaseResultRow).where(CaseResultRow.run_id == run_id)
    if load_full_detail_json:
        load_detail_json = True
    if not load_full_detail_json:
        stmt = stmt.options(load_only(*_LIST_CASE_COLUMNS))
    if level:
        stmt = stmt.where(CaseResultRow.level == level)
    if release_passed is not None:
        stmt = stmt.where(CaseResultRow.release_passed == release_passed)
    if stability:
        stmt = stmt.where(CaseResultRow.stability == stability)
    if scenario:
        stmt = stmt.where(CaseResultRow.scenario == scenario)
    if sample_ids is not None:
        if not sample_ids:
            stmt = stmt.where(False)
        else:
            stmt = stmt.where(CaseResultRow.sample_id.in_(sample_ids))
    if guideline == "full":
        stmt = stmt.where(
            CaseResultRow.guideline_max.is_not(None),
            CaseResultRow.guideline_max > 0,
            CaseResultRow.guideline_earned == CaseResultRow.guideline_max,
        )
    elif guideline == "partial":
        stmt = stmt.where(
            CaseResultRow.guideline_max.is_not(None),
            CaseResultRow.guideline_max > 0,
            (CaseResultRow.guideline_earned.is_(None))
            | (CaseResultRow.guideline_earned != CaseResultRow.guideline_max),
        )
    elif guideline == "none":
        stmt = stmt.where(
            (CaseResultRow.guideline_max.is_(None))
            | (CaseResultRow.guideline_max <= 0)
        )
    if turns == "single":
        stmt = stmt.where(CaseResultRow.n_turns <= 1)
    elif turns == "multi":
        stmt = stmt.where(CaseResultRow.n_turns > 1)
    stmt = stmt.order_by(CaseResultRow.sample_id)
    return stmt


def filtered_case_rows(
    session: Session,
    run_id: int,
    *,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    turns: Optional[str] = None,
    guideline: Optional[str] = None,
    load_detail_json: bool = True,
    load_full_detail_json: bool = False,
) -> list[CaseResultRow]:
    stmt = _filtered_case_stmt(
        run_id,
        level=level,
        release_passed=release_passed,
        stability=stability,
        scenario=scenario,
        turns=turns,
        guideline=guideline,
        load_detail_json=load_detail_json,
        load_full_detail_json=load_full_detail_json,
    )
    rows = list(session.execute(stmt).scalars().all())
    for row in rows:
        _attach_row_display_fields(
            row,
            # 新版已经将轮数/RAG 状态存为标量；除导出等显式要求 full JSON 的路径外，
            # 不读取 detail_json，避免 PostgreSQL 逐条解压大型 Langfuse 快照。
            load_detail_json=load_full_detail_json,
        )
    return rows


def filtered_case_page(
    session: Session,
    run_id: int,
    *,
    limit: int,
    offset: int,
    sample_ids: set[str] | None = None,
    **filters,
) -> tuple[int, list[CaseResultRow]]:
    """SQL 层过滤、计数和分页；列表页不再先加载整批结果后切片。"""
    stmt = _filtered_case_stmt(
        run_id,
        load_detail_json=False,
        load_full_detail_json=False,
        sample_ids=sample_ids,
        **filters,
    )
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int(session.scalar(count_stmt) or 0)
    rows = list(session.scalars(stmt.offset(offset).limit(limit)))
    for row in rows:
        _attach_row_display_fields(row, load_detail_json=False)
    return total, rows


def attach_review_summary(
    session: Session, run_id: int, rows: list[CaseResultRow]
) -> None:
    sample_ids = [row.sample_id for row in rows]
    if not sample_ids:
        return
    ranked = (
        select(
            CaseAnnotation.sample_id.label("sample_id"),
            CaseAnnotation.verdict.label("verdict"),
            CaseAnnotation.reviewer.label("reviewer"),
            CaseAnnotation.suggestion.label("suggestion"),
            CaseAnnotation.comment.label("comment"),
            func.count(CaseAnnotation.id)
            .over(partition_by=CaseAnnotation.sample_id)
            .label("annotation_count"),
            func.row_number()
            .over(
                partition_by=CaseAnnotation.sample_id,
                order_by=(CaseAnnotation.created_at.desc(), CaseAnnotation.id.desc()),
            )
            .label("position"),
        )
        .where(
            CaseAnnotation.run_id == run_id,
            CaseAnnotation.sample_id.in_(sample_ids),
        )
        .subquery()
    )
    summaries = {
        item["sample_id"]: item
        for item in session.execute(
            select(ranked).where(ranked.c.position == 1)
        ).mappings()
    }
    for row in rows:
        latest = summaries.get(row.sample_id)
        if latest:
            row.review = ReviewSummary(
                verdict=latest["verdict"],
                reviewer=latest["reviewer"],
                suggestion=latest["suggestion"],
                comment=latest["comment"],
                count=int(latest["annotation_count"]),
            )
        else:
            row.review = None


def case_scores(d: dict[str, Any]) -> CaseScores:
    d = d or {}
    return CaseScores(
        medical_safety_passed=d.get("medical_safety_passed"),
        release_passed=bool(d.get("release_passed")),
        composite_score=d.get("composite_score"),
        grade=d.get("grade") or "",
        dimension_scores=d.get("dimension_scores") or {},
        dimension_max=d.get("dimension_max") or {},
        dimension_raw_scores=d.get("dimension_raw_scores") or {},
        end_scores=d.get("end_scores") or {},
        guideline_scores=d.get("guideline_scores") or [],
        assertion_scores=d.get("assertion_scores") or [],
        score_deductions=d.get("score_deductions") or [],
        failure_tags=d.get("failure_tags") or [],
        verdicts=[
            {
                "name": v.get("name"),
                "passed": v.get("passed"),
                "score": v.get("score"),
                "max_score": v.get("max_score"),
                "reason": v.get("reason"),
                "evidence": v.get("evidence") or [],
                "details": v.get("details") or {},
            }
            for v in (d.get("verdicts") or [])
        ],
    )


def override_from_yaml(yaml_text: str, sample_id: str) -> dict[str, Any]:
    try:
        docs = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=422,
            detail="YAML 解析失败，请检查缩进、冒号和列表格式",
        ) from exc
    items = docs if isinstance(docs, list) else [docs]
    for it in items:
        if isinstance(it, dict) and it.get("sample_id") == sample_id:
            return {"sample_id": sample_id, "evaluation": it.get("evaluation") or {}}
    raise HTTPException(status_code=400, detail=f"YAML 中未找到用例 {sample_id}")


def queue_reasons(
    row: CaseResultRow,
    *,
    dispersion_threshold: float = 0.5,
    baseline: CaseResultRow | None = None,
    cross_run_comparable: bool = True,
) -> list[str]:
    reasons: list[str] = []
    if not row.release_passed:
        reasons.append("release_failed")
    if row.medical_safety_passed is False:
        reasons.append("medical_safety_failed")
    if baseline is not None and cross_run_comparable:
        from .cross_run_diff import cross_run_diff_reasons

        for tag in cross_run_diff_reasons(row, baseline):
            if tag not in reasons:
                reasons.append(tag)
    return reasons


def case_row_or_404(session: Session, run_id: int, sample_id: str) -> CaseResultRow:
    row = session.execute(
        select(CaseResultRow).where(
            CaseResultRow.run_id == run_id, CaseResultRow.sample_id == sample_id
        )
    ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} 中无用例 {sample_id}")
    return row


def next_case_sample_id(session: Session, run_id: int, sample_id: str) -> str | None:
    """按当前列表排序取下一题，只读取一个标量字段。"""
    row = session.execute(
        select(CaseResultRow.sample_id)
        .where(
            CaseResultRow.run_id == run_id,
            CaseResultRow.sample_id > sample_id,
        )
        .order_by(CaseResultRow.sample_id)
        .limit(1)
    ).scalar_one_or_none()
    return str(row) if row is not None else None
