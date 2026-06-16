"""评测 run 人审校准 API（P1-5）。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..db import get_session
from ..models_db import FeishuUser
from ..settings import get_settings
from ..services.runs import get_run_or_404
from medeval.calibration.agreement import compute_agreement, load_human_scores

router = APIRouter(prefix="/api/runs", tags=["calibration"])


@router.post("/{run_id}/calibration")
async def run_calibration(
    run_id: int,
    human: UploadFile = File(...),
    session: Session = Depends(get_session),
    _user: FeishuUser | None = Depends(get_current_user_optional),
):
    """上传人审打分表（YAML/JSON），与指定 run 的 report.json 对齐计算一致性。"""
    run = get_run_or_404(session, run_id)
    settings = get_settings()
    report_path = settings.outputs_dir / run.run_slug / "report.json"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="该 run 无 report.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suffix = Path(human.filename or "scores.yaml").suffix or ".yaml"
    tmp = Path(f"/tmp/mme_cal_{run_id}{suffix}")
    tmp.write_bytes(await human.read())
    try:
        scores = load_human_scores(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    return compute_agreement(scores, report)
