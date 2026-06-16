"""用例 YAML 导出、飞书流水导出、用例明细。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import HTTPException
from sqlalchemy.orm import Session

from medeval.models import CaseResult, RunReport
from medeval.reporter.excel_transcript import write_transcripts_xlsx

from ..auth import SessionExpired, ensure_fresh_token
from ..benchmarks import load_benchmark_cases
from ..feishu_drive import FeishuDriveError
from ..models_db import Benchmark, FeishuUser
from ..paths import safe_join
from ..schemas import CasesYamlOut
from ..settings import Settings, get_settings
from .case_query import case_row_or_404, filtered_case_rows
from .feishu_transcript_export import import_xlsx_as_sheet, publish_xlsx_to_lark
from .runs import get_run_or_404


def get_cases_yaml(
    session: Session,
    run_id: int,
    *,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    score_profile: Optional[str] = None,
    guideline: Optional[str] = None,
    sample_id: Optional[str] = None,
) -> CasesYamlOut:
    run = get_run_or_404(session, run_id)
    if run.benchmark_id is None:
        raise HTTPException(status_code=400, detail="该评测未关联 benchmark，无法导出用例 YAML")
    bm = session.get(Benchmark, run.benchmark_id)
    if bm is None:
        raise HTTPException(status_code=400, detail="该评测关联的 benchmark 已不存在")

    rows = filtered_case_rows(
        session,
        run_id,
        level=level,
        release_passed=release_passed,
        stability=stability,
        scenario=scenario,
        score_profile=score_profile,
        guideline=guideline,
        load_detail_json=True,
    )
    hit_ids = {r.sample_id for r in rows}
    if sample_id is not None:
        if sample_id not in hit_ids:
            raise HTTPException(
                status_code=400, detail=f"用例 {sample_id} 不在当前过滤命中集"
            )
        hit_ids = {sample_id}
    if not hit_ids:
        raise HTTPException(status_code=400, detail="当前过滤条件下没有命中用例")

    cases = [c for c in load_benchmark_cases(bm) if c.sample_id in hit_ids]
    payload = []
    for c in cases:
        d = c.model_dump(mode="json")
        d.pop("case_file", None)
        payload.append(d)
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    return CasesYamlOut(benchmark_id=bm.id, count=len(cases), yaml_text=text)


def get_case_detail_json(session: Session, run_id: int, sample_id: str) -> dict[str, Any]:
    row = case_row_or_404(session, run_id, sample_id)
    return row.detail_json


def export_transcripts(
    session: Session,
    run_id: int,
    *,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    score_profile: Optional[str] = None,
    guideline: Optional[str] = None,
    parent_folder_token: Optional[str] = None,
    current_user: Optional[FeishuUser] = None,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    run = get_run_or_404(session, run_id)
    rows = filtered_case_rows(
        session,
        run_id,
        level=level,
        release_passed=release_passed,
        stability=stability,
        scenario=scenario,
        score_profile=score_profile,
        guideline=guideline,
    )
    if not rows:
        raise HTTPException(status_code=400, detail="当前过滤条件下没有用例可导出")

    cases = [CaseResult.model_validate(r.detail_json) for r in rows]
    report = RunReport(
        run_name=run.run_slug,
        description=run.description or "",
        adapter_type=run.adapter_type,
        config_snapshot=run.config_snapshot or {},
        results=cases,
        total=len(cases),
    )

    try:
        out_dir = safe_join(settings.outputs_dir, run.run_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法的 run 目录") from exc
    xlsx_path: Path = out_dir / f"{run.run_slug}_transcripts.xlsx"
    write_transcripts_xlsx(report, xlsx_path)

    if parent_folder_token is None:
        token = (
            (run.config_snapshot or {})
            .get("reporter", {})
            .get("lark", {})
            .get("parent_folder_token", "")
        )
    else:
        token = parent_folder_token

    title = run.name or run.run_slug

    if current_user is not None:
        try:
            ensure_fresh_token(session, current_user, settings)
        except SessionExpired:
            raise HTTPException(status_code=401, detail="飞书会话已过期，请重新登录")
        try:
            url = import_xlsx_as_sheet(
                current_user.access_token,
                xlsx_path,
                folder_token=token,
                title=title,
            )
        except FeishuDriveError as e:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"飞书导出失败：{e}。请确认：①已开通 drive:drive 权限；"
                    "②若填写了文件夹 token，你需对该文件夹有写权限；③可留空 token 改为个人根目录。"
                ),
            )
        return {"url": url, "count": len(cases), "filename": xlsx_path.name}

    url = publish_xlsx_to_lark(xlsx_path, parent_folder_token=token, title=title)
    if not url:
        raise HTTPException(
            status_code=502,
            detail=(
                "飞书发布失败。请确认：①已安装并登录 lark-cli（lark-cli auth login）；"
                "②若填写了飞书文件夹 token，当前账号需对该文件夹有写权限；"
                "③可留空 token 改为上传到个人空间根目录。"
            ),
        )
    return {"url": url, "count": len(cases), "filename": xlsx_path.name}
