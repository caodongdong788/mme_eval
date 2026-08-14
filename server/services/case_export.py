"""用例 YAML 导出、飞书流水导出、用例明细。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

import yaml
from fastapi import HTTPException
from sqlalchemy.orm import Session

from medeval.evaluation_accounts import evaluation_account_credentials
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
from .agent_chain_summary import ensure_agent_chain_summary
from .feishu_transcript_export import import_xlsx_as_sheet, publish_xlsx_to_lark
from .runs import get_run_or_404

_RETIRED_CX_SIT_HOST = "10.30.7.71"
_CURRENT_CX_SIT_ORIGIN = ("https", "sit-cx.senzco.com")


def _restore_guideline_dimensions(detail: dict[str, Any]) -> dict[str, Any]:
    """为历史详情中的旧指南评分行恢复绑定维度。

    V2 Case 的 ``evaluation.guidelines`` 已把维度作为必填真值保存；早期落库的
    ``guideline_scores`` 可能漏存该冗余字段，导致页面误显示“未关联维度”。这里只
    按相同 guideline id 从冻结 Case 回填，找不到真值时保持为空，绝不猜测维度。
    """
    case = detail.get("case") if isinstance(detail.get("case"), dict) else {}
    evaluation = case.get("evaluation") if isinstance(case.get("evaluation"), dict) else {}
    guidelines = evaluation.get("guidelines") if isinstance(evaluation.get("guidelines"), list) else []
    dimensions_by_id = {
        str(item.get("id")): str(item.get("dimension"))
        for item in guidelines
        if isinstance(item, dict) and item.get("id") and item.get("dimension")
    }
    scores = detail.get("guideline_scores")
    if not dimensions_by_id or not isinstance(scores, list):
        return detail
    restored = []
    changed = False
    for score in scores:
        if not isinstance(score, dict) or score.get("dimension"):
            restored.append(score)
            continue
        dimension = dimensions_by_id.get(str(score.get("id", "")))
        if not dimension:
            restored.append(score)
            continue
        restored.append({**score, "dimension": dimension})
        changed = True
    return {**detail, "guideline_scores": restored} if changed else detail


def _current_cx_share_url(value: Any) -> Any:
    """把旧 SIT 分享页映射到当前域名；其它 URL 原样返回。"""
    if not isinstance(value, str) or not value:
        return value
    try:
        parsed = urlsplit(value)
        is_retired_share = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname == _RETIRED_CX_SIT_HOST
            and parsed.port in {None, 80, 443}
            and parsed.path.startswith("/s/")
        )
    except ValueError:
        return value
    if not is_retired_share:
        return value
    return urlunsplit((*_CURRENT_CX_SIT_ORIGIN, parsed.path, parsed.query, parsed.fragment))


def get_cases_yaml(
    session: Session,
    run_id: int,
    *,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
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
        guideline=guideline,
        load_detail_json=True,
        load_full_detail_json=True,
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


def _compact_agent_chain_detail(detail: dict[str, Any]) -> dict[str, Any]:
    """移除首屏不消费的原始链路大字段。

    Langfuse observation 的 input/output 可能包含完整系统提示词和 RAG chunk，单个 Case
    可达数百 KB。详情页首屏只使用链路摘要；RAG 全量审计数据改由专用接口按点击加载。
    没有摘要的旧数据才即时补一次，避免每次打开都深拷贝完整节点。
    """
    trace_raw = detail.get("trace")
    trace_raw = trace_raw if isinstance(trace_raw, dict) else {}
    chain_raw = trace_raw.get("agent_chain")
    chain_raw = chain_raw if isinstance(chain_raw, dict) else {}
    source = detail
    if chain_raw and not isinstance(chain_raw.get("summary"), dict):
        source = ensure_agent_chain_summary(detail)
        trace_raw = source.get("trace") if isinstance(source.get("trace"), dict) else {}
        chain_raw = trace_raw.get("agent_chain") if isinstance(trace_raw.get("agent_chain"), dict) else {}

    compact = dict(source)
    if not trace_raw:
        return compact
    trace = dict(trace_raw)
    # 审计快照仅供「查看 RAG 明细」按需读取，首屏不传输。
    trace.pop("cx_literature_audits", None)
    if chain_raw:
        chain = dict(chain_raw)
        chain.pop("nodes", None)
        summary_raw = chain.get("summary")
        if isinstance(summary_raw, dict):
            summary = dict(summary_raw)
            sources_raw = summary.get("sources")
            if isinstance(sources_raw, list):
                summary["sources"] = [
                    {key: value for key, value in source_item.items() if key != "rag_audit"}
                    if isinstance(source_item, dict)
                    else source_item
                    for source_item in sources_raw
                ]
            chain["summary"] = summary
        trace["agent_chain"] = chain
    compact["trace"] = trace
    return compact


def get_case_detail_json(session: Session, run_id: int, sample_id: str) -> dict[str, Any]:
    row = case_row_or_404(session, run_id, sample_id)
    detail = _restore_guideline_dimensions(_compact_agent_chain_detail(row.detail_json or {}))
    trace = detail.get("trace")
    if isinstance(trace, dict):
        trace["cx_evaluation_share_url"] = _current_cx_share_url(
            trace.get("cx_evaluation_share_url")
        )
        identity = trace.get("evaluation_identity")
        if isinstance(identity, dict):
            credentials = evaluation_account_credentials(
                identity.get("test_user_id"),
                login_account=identity.get("login_account"),
            )
            for key, value in credentials.items():
                identity.setdefault(key, value)
    return detail


def get_case_rag_audit_json(session: Session, run_id: int, sample_id: str) -> dict[str, Any]:
    """按需返回完整 RAG 审计快照，不拖慢 Case 明细首屏。"""
    row = case_row_or_404(session, run_id, sample_id)
    detail = ensure_agent_chain_summary(row.detail_json or {})
    trace = detail.get("trace") if isinstance(detail.get("trace"), dict) else {}
    chain = trace.get("agent_chain") if isinstance(trace.get("agent_chain"), dict) else {}
    summary = chain.get("summary") if isinstance(chain.get("summary"), dict) else {}
    sources = summary.get("sources") if isinstance(summary.get("sources"), list) else []
    rag = next(
        (
            item
            for item in sources
            if isinstance(item, dict) and item.get("key") == "literature_rag"
        ),
        {},
    )
    audits = rag.get("rag_audit") if isinstance(rag.get("rag_audit"), list) else []
    return {"calls": audits}


def export_transcripts(
    session: Session,
    run_id: int,
    *,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
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
        guideline=guideline,
        load_full_detail_json=True,
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
