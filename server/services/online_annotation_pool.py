"""线上评测标注池：收集满意 case，并按标注集导出飞书清单。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import feishu_sheet
from ..auth import SessionExpired, ensure_fresh_token
from ..benchmarks import _cell_text, _feishu_row_turns, _sheet_row_fields, _user_profile_text
from ..feishu_drive import FeishuDriveError
from ..models_db import (
    FeishuUser,
    OnlineAnnotationPoolCase,
    OnlineAnnotationPoolPath,
    OnlineEvalCase,
)
from ..paths import safe_join
from ..settings import Settings, get_settings
from .online_eval_export import (
    _build_image_fetcher,
    _write_cases_xlsx,
    import_xlsx_as_sheet,
    publish_xlsx_to_lark,
)


def _normalise_path(path: str) -> str:
    parts = [
        part.strip()
        for part in (path or "").replace("\\", "/").split("/")
        if part.strip()
    ]
    normalised = "/".join(parts)
    if not normalised:
        raise HTTPException(status_code=422, detail="请输入标注集名称")
    if len(normalised) > 300:
        raise HTTPException(status_code=422, detail="标注集名称过长")
    return normalised


def _safe_filename(text: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", text).strip("_")
    return name or "annotation_pool"


def _role_from_sheet_name(sheet_name: str) -> str:
    lowered = (sheet_name or "").strip().lower()
    if "医生" in lowered or "doctor" in lowered:
        return "doctor"
    if "护士" in lowered or "nurse" in lowered:
        return "nurse"
    return "patient"


def _preview_title(text: str, fallback: str) -> str:
    text = " ".join((text or "").split())
    if not text:
        return fallback
    return text[:80]


def _first_user_question(raw_messages: list[Any], fallback: str = "") -> str:
    for msg in raw_messages or []:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "user":
            text = str(msg.get("content") or "").strip()
            if text:
                return text
    for line in (fallback or "").splitlines():
        text = line.strip()
        if text:
            return text
    return ""


def _grade_from_score(score: float, gate_status: str) -> str:
    if gate_status in {"fail", "need_human_review"}:
        return "unqualified"
    if score >= 40.5:
        return "excellent"
    if score >= 36:
        return "good"
    if score >= 27:
        return "qualified"
    return "unqualified"


def _normalise_case_snapshot(case: OnlineAnnotationPoolCase) -> None:
    case.case_name = (
        _first_user_question(case.raw_messages or [], case.user_text)
        or case.case_name
        or case.external_id
    )
    if case.source_eval_id or case.grade:
        case.grade = _grade_from_score(float(case.total_score or 0.0), case.gate_status or "")


def _row_number(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _cases_from_feishu_sheets(
    *,
    path_id: int,
    sheets: list[dict[str, Any]],
    created_by: str | None,
) -> list[OnlineAnnotationPoolCase]:
    rows: list[OnlineAnnotationPoolCase] = []
    for sheet_index, sheet in enumerate(sheets):
        cells = sheet.get("cells") or []
        row_indices = sheet.get("row_indices") or []
        if not cells or not isinstance(cells, list):
            continue
        headers = [_cell_text(cell) for cell in cells[0]]
        sheet_name = str(sheet.get("sheet_name") or sheet.get("sheet_id") or "Sheet").strip()
        review_role = _role_from_sheet_name(sheet_name)

        for row_index, row in enumerate(cells[1:], start=1):
            if not isinstance(row, list):
                continue
            fields = _sheet_row_fields(headers, row)
            raw_messages: list[dict[str, str]] = []
            user_parts: list[str] = []
            assistant_parts: list[str] = []
            for turn in _feishu_row_turns(fields):
                role = turn["role"]
                content = str(turn["content"])
                raw_messages.append({"role": role, "content": content})
                if role == "user":
                    user_parts.append(content)
                elif role == "assistant":
                    assistant_parts.append(content)
            if not raw_messages:
                continue

            row_number = row_indices[row_index] if row_index < len(row_indices) else row_index + 1
            numeric_row = _row_number(row_number, row_index + 1)
            external_id = f"feishu_sheet:{sheet_name}:{row_number}"
            source_case_id = -((sheet_index + 1) * 1_000_000 + numeric_row)
            rows.append(
                OnlineAnnotationPoolCase(
                    path_id=path_id,
                    source_eval_id=0,
                    source_case_id=source_case_id,
                    external_id=external_id,
                    case_name=_preview_title(user_parts[0] if user_parts else "", external_id),
                    user_text="\n\n".join(user_parts),
                    assistant_text="\n\n".join(assistant_parts),
                    raw_messages=raw_messages,
                    user_profile=_user_profile_text(fields),
                    task_type="general_support",
                    review_role=review_role,
                    gate_status="pass",
                    total_score=0.0,
                    grade="",
                    score_breakdown={},
                    dimension_scores={},
                    dimension_feedback={},
                    risk_tags=[],
                    evidence=[],
                    improvement_suggestions=[],
                    benchmark_candidate=True,
                    created_by=created_by,
                )
            )
    return rows


def list_paths(session: Session) -> list[OnlineAnnotationPoolPath]:
    paths = list(
        session.scalars(
            select(OnlineAnnotationPoolPath).order_by(OnlineAnnotationPoolPath.path.asc())
        )
    )
    if not paths:
        return []
    counts = dict(
        session.execute(
            select(
                OnlineAnnotationPoolCase.path_id,
                func.count(OnlineAnnotationPoolCase.id),
            ).group_by(OnlineAnnotationPoolCase.path_id)
        ).all()
    )
    for path in paths:
        path.case_count = int(counts.get(path.id, 0))  # type: ignore[attr-defined]
    return paths


def create_path(
    session: Session,
    *,
    path: str,
    description: str = "",
    created_by: str | None = None,
) -> OnlineAnnotationPoolPath:
    normalised = _normalise_path(path)
    exists = session.scalar(
        select(OnlineAnnotationPoolPath).where(OnlineAnnotationPoolPath.path == normalised)
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="该标注集已存在")
    row = OnlineAnnotationPoolPath(
        path=normalised,
        description=description.strip(),
        created_by=created_by,
    )
    session.add(row)
    session.flush()
    row.case_count = 0  # type: ignore[attr-defined]
    return row


def import_path_from_feishu_url(
    session: Session,
    *,
    path: str,
    description: str = "",
    source_url: str,
    current_user: FeishuUser | None,
    settings: Settings | None = None,
) -> OnlineAnnotationPoolPath:
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录飞书后再导入")
    settings = settings or get_settings()
    try:
        ensure_fresh_token(session, current_user, settings)
    except SessionExpired:
        raise HTTPException(status_code=401, detail="飞书会话已过期，请重新登录")
    try:
        sheets = feishu_sheet.fetch_sheet_cells(current_user.access_token, source_url)
    except feishu_sheet.FeishuSheetError as exc:
        raise HTTPException(status_code=502, detail=f"读取飞书表格失败：{exc}") from exc

    pool_path = create_path(
        session,
        path=path,
        description=description,
        created_by=current_user.name or None,
    )
    rows = _cases_from_feishu_sheets(
        path_id=pool_path.id,
        sheets=sheets,
        created_by=current_user.name or None,
    )
    if not rows:
        raise HTTPException(status_code=422, detail="飞书表格中没有可导入的对话")
    session.add_all(rows)
    session.flush()
    pool_path.case_count = len(rows)  # type: ignore[attr-defined]
    return pool_path


def update_path(
    session: Session,
    path_id: int,
    *,
    path: str,
    description: str = "",
) -> OnlineAnnotationPoolPath:
    row = session.get(OnlineAnnotationPoolPath, path_id)
    if row is None:
        raise HTTPException(status_code=404, detail="标注集不存在")
    normalised = _normalise_path(path)
    exists = session.scalar(
        select(OnlineAnnotationPoolPath).where(
            OnlineAnnotationPoolPath.path == normalised,
            OnlineAnnotationPoolPath.id != path_id,
        )
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="该标注集已存在")
    row.path = normalised
    row.description = description.strip()
    session.flush()
    count = session.scalar(
        select(func.count(OnlineAnnotationPoolCase.id)).where(
            OnlineAnnotationPoolCase.path_id == path_id
        )
    )
    row.case_count = int(count or 0)  # type: ignore[attr-defined]
    return row


def delete_path(session: Session, path_id: int) -> None:
    pool_path = session.get(OnlineAnnotationPoolPath, path_id)
    if pool_path is None:
        raise HTTPException(status_code=404, detail="标注集不存在")
    session.delete(pool_path)
    session.flush()


def _snapshot_case(
    *,
    path_id: int,
    source: OnlineEvalCase,
    created_by: str | None,
) -> OnlineAnnotationPoolCase:
    row = OnlineAnnotationPoolCase(
        path_id=path_id,
        source_eval_id=source.online_eval_id,
        source_case_id=source.id,
        external_id=source.external_id,
        case_name=_first_user_question(source.raw_messages or [], source.user_text)
        or source.case_name,
        user_text=source.user_text,
        assistant_text=source.assistant_text,
        raw_messages=source.raw_messages or [],
        user_profile=source.user_profile or "",
        task_type=source.task_type,
        review_role=source.review_role,
        gate_status=source.gate_status,
        total_score=source.total_score,
        grade=_grade_from_score(float(source.total_score or 0.0), source.gate_status or ""),
        score_breakdown=source.score_breakdown or {},
        dimension_scores=source.dimension_scores or {},
        dimension_feedback=source.dimension_feedback or {},
        risk_tags=source.risk_tags or [],
        evidence=source.evidence or [],
        improvement_suggestions=source.improvement_suggestions or [],
        benchmark_candidate=source.benchmark_candidate,
        created_by=created_by,
    )
    _normalise_case_snapshot(row)
    return row


def add_case(
    session: Session,
    *,
    path_id: int,
    online_eval_case_id: int,
    created_by: str | None = None,
) -> OnlineAnnotationPoolCase:
    pool_path = session.get(OnlineAnnotationPoolPath, path_id)
    if pool_path is None:
        raise HTTPException(status_code=404, detail="标注集不存在")
    source = session.get(OnlineEvalCase, online_eval_case_id)
    if source is None:
        raise HTTPException(status_code=404, detail="线上评测 case 不存在")
    exists = session.scalar(
        select(OnlineAnnotationPoolCase).where(
            OnlineAnnotationPoolCase.path_id == path_id,
            OnlineAnnotationPoolCase.source_case_id == online_eval_case_id,
        )
    )
    if exists is not None:
        return exists
    row = _snapshot_case(path_id=path_id, source=source, created_by=created_by)
    session.add(row)
    session.flush()
    return row


def list_cases(session: Session, path_id: int) -> list[OnlineAnnotationPoolCase]:
    if session.get(OnlineAnnotationPoolPath, path_id) is None:
        raise HTTPException(status_code=404, detail="标注集不存在")
    rows = list(
        session.scalars(
            select(OnlineAnnotationPoolCase)
            .where(OnlineAnnotationPoolCase.path_id == path_id)
            .order_by(OnlineAnnotationPoolCase.created_at.desc(), OnlineAnnotationPoolCase.id.desc())
        )
    )
    for row in rows:
        _normalise_case_snapshot(row)
    return rows


def delete_case(session: Session, path_id: int, case_id: int) -> None:
    pool_path = session.get(OnlineAnnotationPoolPath, path_id)
    if pool_path is None:
        raise HTTPException(status_code=404, detail="标注集不存在")
    case = session.get(OnlineAnnotationPoolCase, case_id)
    if case is None or case.path_id != path_id:
        raise HTTPException(status_code=404, detail="标注集 case 不存在")
    session.delete(case)
    session.flush()


def export_path_cases(
    session: Session,
    path_id: int,
    *,
    parent_folder_token: Optional[str] = None,
    current_user: Optional[FeishuUser] = None,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    pool_path = session.get(OnlineAnnotationPoolPath, path_id)
    if pool_path is None:
        raise HTTPException(status_code=404, detail="标注集不存在")
    cases = list_cases(session, path_id)
    if not cases:
        raise HTTPException(status_code=400, detail="该标注集下没有可导出的 case")

    image_fetcher = None
    if current_user is not None:
        try:
            ensure_fresh_token(session, current_user, settings)
        except SessionExpired:
            raise HTTPException(status_code=401, detail="飞书会话已过期，请重新登录")
        image_fetcher = _build_image_fetcher(current_user.access_token)

    try:
        out_dir = safe_join(settings.outputs_dir, "online_annotation_pool_exports")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法的导出目录") from exc
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename_prefix = _safe_filename(pool_path.path)
    xlsx_path = out_dir / f"{filename_prefix}_{timestamp}.xlsx"
    _write_cases_xlsx(cases, xlsx_path, image_fetcher)

    token = "" if parent_folder_token is None else parent_folder_token
    title = f"{pool_path.path.replace('/', '_')}_标注池清单"
    if current_user is not None:
        try:
            url = import_xlsx_as_sheet(
                current_user.access_token,
                xlsx_path,
                folder_token=token,
                title=title,
            )
        except FeishuDriveError as exc:
            raise HTTPException(status_code=502, detail=f"飞书导出失败：{exc}")
        return {"url": url, "count": len(cases), "filename": xlsx_path.name}

    url = publish_xlsx_to_lark(xlsx_path, parent_folder_token=token, title=title)
    if not url:
        raise HTTPException(status_code=502, detail="飞书发布失败，请先登录飞书后重试")
    return {"url": url, "count": len(cases), "filename": xlsx_path.name}
