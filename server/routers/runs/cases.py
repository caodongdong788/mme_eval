"""runs 用例列表、明细、YAML 导出与飞书流水。"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from medeval.models import ConversationTrace

from ...auth import get_current_user_optional
from ...constants import LIST_LIMIT_DEFAULT, LIST_LIMIT_MAX
from ...db import get_session
from ...models_db import Benchmark, CaseResultRow, FeishuUser
from ...paths import safe_join
from ...schemas import CaseRowOut, CasesYamlOut
from ...services.case_export import (
    export_transcripts,
    get_case_detail_json,
    get_case_rag_audit_json,
    get_cases_yaml,
)
from ...services.case_query import (
    attach_review_summary,
    case_rag_status_from_detail,
    filtered_case_rows,
)
from ...services.case_query import case_row_or_404, next_case_sample_id
from ...services.eval_artifacts import CASE_IMAGES_DIR
from ...services.langfuse_trace import sync_conversation_trace
from ...services.review import pending_review_sample_ids
from ...services.runs import get_run_or_404, source_out_dir
from ...settings import get_settings
from ._router import router


_CASE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_MARKDOWN_IMAGE_PATH_RE = re.compile(r"!\[[^\]]*\]\(\s*(images/[^\s)]+)", re.IGNORECASE)


def _case_image_paths(detail: dict[str, Any]) -> set[str]:
    """取冻结 Case 声明的图片路径，避免图片接口被用于任意读文件。"""
    case = detail.get("case") or {}
    turns = case.get("turns") if isinstance(case, dict) else []
    paths: set[str] = set()
    for turn in turns if isinstance(turns, list) else []:
        if not isinstance(turn, dict):
            continue
        images = turn.get("images") or []
        if isinstance(images, list):
            paths.update(item for item in images if isinstance(item, str))
        content = turn.get("content")
        if isinstance(content, str):
            paths.update(_MARKDOWN_IMAGE_PATH_RE.findall(content))
    return paths


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
        # 轮数及真实 RAG 状态均已写入列表标量列，避免此接口读取整批大型链路 JSON。
        load_detail_json=False,
    )
    # Langfuse 深链仍仅在用例详情接口返回，避免扩大列表响应中的外部追踪信息。
    for row in rows:
        row.langfuse_trace_url = None
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


@router.get("/{run_id}/cases/{sample_id}/next")
def get_next_case(
    run_id: int,
    sample_id: str,
    session: Session = Depends(get_session),
) -> dict[str, str | None]:
    get_run_or_404(session, run_id)
    return {"sample_id": next_case_sample_id(session, run_id, sample_id)}


@router.get("/{run_id}/cases/{sample_id}/agent-chain/rag-audit")
def get_case_rag_audit(
    run_id: int,
    sample_id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return get_case_rag_audit_json(session, run_id, sample_id)


@router.get("/{run_id}/cases/{sample_id}/images/{image_path:path}")
def get_case_image(
    run_id: int, sample_id: str, image_path: str, session: Session = Depends(get_session)
) -> FileResponse:
    """返回当前 Case 在 ZIP benchmark 中声明的图片，用于评测流水预览。"""
    row = case_row_or_404(session, run_id, sample_id)
    normalized_path = image_path.replace("\\", "/")
    relative = Path(normalized_path)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not relative.parts
        or relative.parts[0] != "images"
        or relative.suffix.lower() not in _CASE_IMAGE_SUFFIXES
    ):
        raise HTTPException(status_code=404, detail="图片不存在")
    if normalized_path not in _case_image_paths(row.detail_json or {}):
        raise HTTPException(status_code=404, detail="图片未在该 Case 中声明")

    run = get_run_or_404(session, run_id)
    run_dir = source_out_dir(run)
    if run_dir is not None:
        try:
            image_file = safe_join(run_dir / CASE_IMAGES_DIR, normalized_path)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="图片不存在") from exc
        if image_file.is_file():
            media_type = mimetypes.guess_type(image_file.name)[0] or "application/octet-stream"
            return FileResponse(image_file, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})

    benchmark = session.get(Benchmark, run.benchmark_id) if run.benchmark_id else None
    if benchmark is None:
        raise HTTPException(status_code=404, detail="该评测关联的 benchmark 不存在")
    storage_root = Path(benchmark.storage_path)
    if not storage_root.is_absolute():
        storage_root = get_settings().project_root / storage_root
    try:
        image_file = safe_join(storage_root, normalized_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="图片不存在") from exc
    if not image_file.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    media_type = mimetypes.guess_type(image_file.name)[0] or "application/octet-stream"
    return FileResponse(image_file, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


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
    row.rag_status = case_rag_status_from_detail(detail)
    session.flush()
    return get_case_detail_json(session, run_id, sample_id)
