"""runs 用例列表、明细、YAML 导出与飞书流水。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from medeval.models import ConversationTrace

from ...auth import get_current_user_optional
from ...constants import LIST_LIMIT_DEFAULT, LIST_LIMIT_MAX
from ...db import get_session
from ...models_db import CaseResultRow, FeishuUser
from ...schemas import CaseRowOut, CasesYamlOut
from ...services.case_export import export_transcripts, get_case_detail_json, get_cases_yaml
from ...services.case_query import attach_review_summary, filtered_case_rows
from ...services.case_query import case_row_or_404
from ...services.langfuse_trace import sync_conversation_trace
from ...services.review import pending_review_sample_ids
from ...services.runs import get_run_or_404
from ...settings import get_settings
from ._router import router


@router.get("/{run_id}/cases", response_model=list[CaseRowOut])
def list_case_results(
    run_id: int,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    turns: Optional[str] = None,
    guideline: Optional[str] = None,
    review_pending: Optional[bool] = None,
    limit: int = Query(
        LIST_LIMIT_DEFAULT, ge=1, le=LIST_LIMIT_MAX, description="分页大小"
    ),
    offset: int = Query(0, ge=0, description="分页偏移"),
    session: Session = Depends(get_session),
) -> list[CaseResultRow]:
    get_run_or_404(session, run_id)
    rows = filtered_case_rows(
        session,
        run_id,
        level=level,
        release_passed=release_passed,
        stability=stability,
        scenario=scenario,
        turns=turns,
        guideline=guideline,
        load_detail_json=False,
    )
    if review_pending:
        pending_ids = pending_review_sample_ids(
            session,
            run_id,
            level=level,
            release_passed=release_passed,
            stability=stability,
            scenario=scenario,
            turns=turns,
            guideline=guideline,
        )
        rows = [r for r in rows if r.sample_id in pending_ids]
    attach_review_summary(session, run_id, rows)
    return rows[offset : offset + limit]


@router.get("/{run_id}/cases-yaml", response_model=CasesYamlOut)
def get_cases_yaml_route(
    run_id: int,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    guideline: Optional[str] = None,
    sample_id: Optional[str] = None,
    session: Session = Depends(get_session),
) -> CasesYamlOut:
    return get_cases_yaml(
        session,
        run_id,
        level=level,
        release_passed=release_passed,
        stability=stability,
        scenario=scenario,
        guideline=guideline,
        sample_id=sample_id,
    )


@router.post("/{run_id}/export-transcripts")
def export_transcripts_route(
    run_id: int,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    guideline: Optional[str] = None,
    parent_folder_token: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> dict[str, Any]:
    return export_transcripts(
        session,
        run_id,
        level=level,
        release_passed=release_passed,
        stability=stability,
        scenario=scenario,
        guideline=guideline,
        parent_folder_token=parent_folder_token,
        current_user=current_user,
    )


@router.get("/{run_id}/cases/{sample_id}")
def get_case_detail(
    run_id: int, sample_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    return get_case_detail_json(session, run_id, sample_id)


@router.post("/{run_id}/cases/{sample_id}/agent-chain/sync")
async def sync_case_agent_chain(
    run_id: int, sample_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """重新从 Langfuse 拉取该 Case 的 cx-agent 内部调用链；失败不改评分。"""
    row = case_row_or_404(session, run_id, sample_id)
    detail = dict(row.detail_json or {})
    trace = ConversationTrace.model_validate(detail.get("trace") or {"messages": []})
    await sync_conversation_trace(trace, get_settings())
    detail["trace"] = trace.model_dump(mode="json")
    row.detail_json = detail
    session.flush()
    return get_case_detail_json(session, run_id, sample_id)
