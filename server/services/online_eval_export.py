"""线上评测清单导出：按筛选条件生成 xlsx 并发布为飞书表格。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy.orm import Session

from ..auth import SessionExpired, ensure_fresh_token
from ..feishu_drive import FeishuDriveError
from ..models_db import FeishuUser, OnlineEvalCase
from ..paths import safe_join
from ..settings import Settings, get_settings
from .feishu_transcript_export import import_xlsx_as_sheet, publish_xlsx_to_lark
from .online_evals import get_online_eval_detail

_ORDINAL_PREFIX = [
    "第一",
    "第二",
    "第三",
    "第四",
    "第五",
    "第六",
    "第七",
    "第八",
    "第九",
    "第十",
    "第十一",
    "第十二",
    "第十三",
    "第十四",
    "第十五",
    "第十六",
    "第十七",
    "第十八",
    "第十九",
    "第二十",
]


def split_filter_values(raw: Optional[str]) -> list[str]:
    """解析前端传来的逗号分隔筛选值。"""
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _score_matches(score: float, bucket: str) -> bool:
    if bucket == "gte9":
        return score >= 9
    if bucket == "8to9":
        return 8 <= score < 9
    if bucket == "7to8":
        return 7 <= score < 8
    if bucket == "6to7":
        return 6 <= score < 7
    if bucket == "lt6":
        return score < 6
    return False


def _matches_any_score_bucket(score: float, buckets: Iterable[str]) -> bool:
    selected = list(buckets)
    return not selected or any(_score_matches(score, bucket) for bucket in selected)


def filter_online_eval_cases(
    cases: list[OnlineEvalCase],
    *,
    gate_statuses: list[str] | None = None,
    score_buckets: list[str] | None = None,
    grades: list[str] | None = None,
) -> list[OnlineEvalCase]:
    """按详情表当前筛选条件过滤 case；列间 AND，列内多选 OR。"""
    gates = gate_statuses or []
    scores = score_buckets or []
    selected_grades = grades or []
    return [
        case
        for case in cases
        if (not gates or case.gate_status in gates)
        and _matches_any_score_bucket(case.total_score_10, scores)
        and (not selected_grades or case.grade in selected_grades)
    ]


def _round_prefix(index: int) -> str:
    if 1 <= index <= len(_ORDINAL_PREFIX):
        return _ORDINAL_PREFIX[index - 1]
    return f"第{index}"


def _case_title(case: OnlineEvalCase) -> str:
    return case.case_name or case.external_id or f"case-{case.id}"


def _append_assistant(turns: list[list[str]], content: str) -> None:
    if not turns:
        turns.append(["", content])
        return
    if turns[-1][1]:
        turns[-1][1] = f"{turns[-1][1]}\n{content}"
    else:
        turns[-1][1] = content


def case_dialogue_turns(case: OnlineEvalCase) -> list[tuple[str, str]]:
    """将 raw_messages 还原成按轮次排列的「用户输入 / Cx 输出」。"""
    turns: list[list[str]] = []
    raw_messages = case.raw_messages if isinstance(case.raw_messages, list) else []
    for msg in raw_messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "").strip()
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            turns.append([content, ""])
        elif role in {"assistant", "bot", "cx"}:
            _append_assistant(turns, content)

    if not turns:
        user_text = (case.user_text or "").strip()
        assistant_text = (case.assistant_text or "").strip()
        if user_text or assistant_text:
            turns.append([user_text, assistant_text])

    return [(user, assistant) for user, assistant in turns]


def _headers(max_turns: int) -> list[str]:
    headers = ["会话标题"]
    for index in range(1, max_turns + 1):
        prefix = _round_prefix(index)
        headers.extend([f"{prefix}轮用户输入", f"{prefix}轮Cx输出"])
    return headers


def _write_cases_xlsx(cases: list[OnlineEvalCase], xlsx_path: Path) -> None:
    rows = [(case, case_dialogue_turns(case)) for case in cases]
    max_turns = max((len(turns) for _case, turns in rows), default=1)

    wb = Workbook()
    ws = wb.active
    ws.title = "评测清单"
    ws.append(_headers(max_turns))

    for case, turns in rows:
        row: list[Any] = [_case_title(case)]
        for index in range(max_turns):
            if index < len(turns):
                row.extend([turns[index][0], turns[index][1]])
            else:
                row.extend(["", ""])
        ws.append(row)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    header_fill = PatternFill(fill_type="solid", fgColor="EAF2FF")
    header_font = Font(bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
    ws.column_dimensions["A"].width = 24
    for column_cells in ws.iter_cols(min_col=2, max_col=ws.max_column):
        ws.column_dimensions[column_cells[0].column_letter].width = 42

    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(xlsx_path)


def export_online_eval_cases(
    session: Session,
    eval_id: int,
    *,
    gate_statuses: list[str] | None = None,
    score_buckets: list[str] | None = None,
    grades: list[str] | None = None,
    parent_folder_token: Optional[str] = None,
    current_user: Optional[FeishuUser] = None,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    row = get_online_eval_detail(session, eval_id)
    cases = filter_online_eval_cases(
        row.cases,
        gate_statuses=gate_statuses,
        score_buckets=score_buckets,
        grades=grades,
    )
    if not cases:
        raise HTTPException(status_code=400, detail="当前过滤条件下没有可导出的线上评测 case")

    try:
        out_dir = safe_join(settings.outputs_dir, "online_eval_exports")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法的导出目录") from exc
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    xlsx_path = out_dir / f"online_eval_{eval_id}_cases_{timestamp}.xlsx"
    _write_cases_xlsx(cases, xlsx_path)

    token = "" if parent_folder_token is None else parent_folder_token
    title = f"{row.name or f'线上评测_{eval_id}'}_评测清单"

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
        except FeishuDriveError as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"飞书导出失败：{exc}。请确认：①已开通 drive:drive 权限；"
                    "②当前账号对目标文件夹有写权限；③可留空 token 改为个人根目录。"
                ),
            )
        return {"url": url, "count": len(cases), "filename": xlsx_path.name}

    url = publish_xlsx_to_lark(xlsx_path, parent_folder_token=token, title=title)
    if not url:
        raise HTTPException(
            status_code=502,
            detail=(
                "飞书发布失败。请确认已安装并登录 lark-cli，或先用飞书账号登录平台后重试。"
            ),
        )
    return {"url": url, "count": len(cases), "filename": xlsx_path.name}
