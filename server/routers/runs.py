"""runs 路由：发起评测 / 列表 / 详情 / 进度 / 用例结果 / 用例明细 / 两次对比。"""

from __future__ import annotations

import shutil
from datetime import datetime
from typing import Any, Optional

import yaml
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from medeval import retention, trace_store
from medeval.models import CaseResult, RunReport
from medeval.reporter.excel_transcript import write_transcripts_xlsx
from medeval.reporter.lark_sheet_publisher import publish_xlsx_to_lark

from ..auth import SessionExpired, ensure_fresh_token, get_current_user_optional
from ..benchmarks import BenchmarkValidationError, load_benchmark_cases
from ..compare import compare_runs
from ..db import get_session
from ..eval_job import (
    build_eval_job,
    build_rejudge_job,
    build_resume_job,
    preview_rejudge_case,
)
from ..feishu_drive import FeishuDriveError, import_xlsx_as_sheet
from ..jobs import get_job_runner
from ..paths import safe_join
from ..models_db import (
    Benchmark,
    CaseAnnotation,
    CaseResultRow,
    EvalRun,
    FeishuUser,
    JudgeModelConfig,
)
from ..settings import get_settings
from ..schemas import (
    AnnotateRequest,
    AnnotationOut,
    CaseRowOut,
    CaseScores,
    CasesYamlOut,
    JudgeOverride,
    PreviewRejudgeRequest,
    PreviewRejudgeResponse,
    ProgressOut,
    RejudgeRequest,
    ReviewQueueItemOut,
    ReviewStatsOut,
    ReviewSummary,
    RunCreate,
    RunDetailOut,
    RunRenameRequest,
    RunSummaryOut,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _get_run_or_404(session: Session, run_id: int) -> EvalRun:
    run = session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} 不存在")
    return run


@router.post("", response_model=RunSummaryOut, status_code=201)
async def create_run(
    payload: RunCreate, session: Session = Depends(get_session)
) -> EvalRun:
    bm = session.get(Benchmark, payload.benchmark_id)
    if bm is None:
        raise HTTPException(
            status_code=404, detail=f"benchmark {payload.benchmark_id} 不存在"
        )

    # 名称唯一性：最终名称（run_name 或缺省 benchmark 名）不得与已有 run 重名。
    final_name = payload.run_name or bm.name
    exists = session.execute(
        select(EvalRun.id).where(EvalRun.name == final_name)
    ).first()
    if exists is not None:
        raise HTTPException(
            status_code=409, detail=f"评测名称「{final_name}」已存在，请换一个名称"
        )

    # 解析判分模型：选中已保存配置时，由服务端据其构建 judge 覆盖（含 Key，注入运行期）。
    judge_ov = payload.judge or JudgeOverride()
    if payload.judge_model_id is not None:
        jm = session.get(JudgeModelConfig, payload.judge_model_id)
        if jm is None:
            raise HTTPException(
                status_code=404, detail=f"判分模型 {payload.judge_model_id} 不存在"
            )
        judge_ov = JudgeOverride(
            enabled=judge_ov.enabled,
            provider=jm.provider or None,
            model=jm.model or None,
            base_url=jm.base_url or None,
            api_version=jm.api_version or None,
            api_key=jm.api_key or None,
            temperature=jm.temperature,
        )
    has_judge = payload.judge is not None or payload.judge_model_id is not None
    judge_public = judge_ov.public_dict() if has_judge else {}
    adapter_public = payload.adapter.public_dict() if payload.adapter else {}

    run = EvalRun(
        run_slug="(pending)",
        name=final_name,
        status="pending",
        benchmark_id=bm.id,
        judge_overrides=judge_public,
        adapter_overrides=adapter_public,
        n_runs=payload.repeat or 1,
    )
    session.add(run)
    session.flush()
    session.commit()  # 让后台任务能在独立会话里看到这一行
    run_id = run.id

    judge_full = judge_ov.model_dump(exclude_none=True) if has_judge else None
    adapter_full = (
        payload.adapter.model_dump(exclude_none=True) if payload.adapter else None
    )
    job = build_eval_job(
        run_id,
        benchmark_id=bm.id,
        run_name=payload.run_name,
        score_profiles=payload.score_profiles,
        levels=payload.levels,
        limit=payload.limit,
        repeat=payload.repeat,
        judge_full=judge_full,
        adapter_full=adapter_full,
    )
    await get_job_runner().submit(run_id, job)
    return run


@router.get("", response_model=list[RunSummaryOut])
def list_runs(
    benchmark_id: Optional[int] = None,
    limit: Optional[int] = Query(None, ge=1, le=1000, description="分页大小，缺省返回全部"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    session: Session = Depends(get_session),
) -> list[EvalRun]:
    """评测列表（倒序）。不带分页参数时行为与既有一致（返回全部）。"""
    stmt = select(EvalRun).order_by(EvalRun.id.desc())
    if benchmark_id is not None:
        stmt = stmt.where(EvalRun.benchmark_id == benchmark_id)
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars().all())


@router.get("/{run_id}", response_model=RunDetailOut)
def get_run(run_id: int, session: Session = Depends(get_session)) -> EvalRun:
    return _get_run_or_404(session, run_id)


@router.delete("/{run_id}", status_code=204)
def delete_run(run_id: int, session: Session = Depends(get_session)) -> None:
    """删除 run 及其级联用例结果，并清理 outputs 产物目录；运行中/等待中不可删除。"""
    run = _get_run_or_404(session, run_id)
    if run.status in ("running", "pending"):
        raise HTTPException(status_code=400, detail="运行中或等待中的评测不可删除，请等待完成")
    # 清理产物目录（经 safe_join 限定在 outputs 根目录内，避免越界误删）。
    run_slug = run.run_slug
    if run_slug and run_slug != "(pending)":
        try:
            out_dir = safe_join(get_settings().outputs_dir, run_slug)
        except ValueError:
            out_dir = None
        if out_dir is not None:
            shutil.rmtree(out_dir, ignore_errors=True)
    session.delete(run)


def _source_out_dir(run: EvalRun) -> Optional[Any]:
    """源 run 的产物目录（经 safe_join 限定在 outputs 根目录内）。slug 缺失/越界返回 None。"""
    slug = run.run_slug
    if not slug or slug == "(pending)":
        return None
    try:
        return safe_join(get_settings().outputs_dir, slug)
    except ValueError:
        return None


def _create_derived_run(
    session: Session,
    source: EvalRun,
    *,
    suffix: str,
    extra_judge_overrides: Optional[dict[str, Any]] = None,
) -> EvalRun:
    """为重判/续跑新建一行 pending EvalRun，沿用源 run 的 benchmark/覆盖/n_runs。

    名称用时间戳后缀避免与既有 run 撞名（满足发起评测名称唯一性约束）。
    extra_judge_overrides：本次重判额外覆盖的 judge 公共参数（已剔除 api_key），合并入展示。
    """
    base = source.name or source.run_slug
    name = f"{base} · {suffix} {datetime.now().strftime('%m%d-%H%M%S')}"
    judge_overrides = dict(source.judge_overrides or {})
    if extra_judge_overrides:
        judge_overrides.update(extra_judge_overrides)
    derived = EvalRun(
        run_slug="(pending)",
        name=name,
        status="pending",
        benchmark_id=source.benchmark_id,
        judge_overrides=judge_overrides,
        adapter_overrides=dict(source.adapter_overrides or {}),
        n_runs=source.n_runs or 1,
        parent_run_id=source.id,
    )
    session.add(derived)
    session.flush()
    session.commit()  # 让后台任务能在独立会话里看到这一行
    return derived


@router.post("/{run_id}/rejudge", response_model=RunSummaryOut, status_code=201)
async def rejudge_run(
    run_id: int,
    payload: Optional[RejudgeRequest] = Body(default=None),
    session: Session = Depends(get_session),
) -> EvalRun:
    """离线重判：对源 run 冻结用例 + 冻结留痕仅重跑判分（零 bot 调用），产出新 run。

    可选 body 临时覆盖判分口径 / judge 模型 / 用某 benchmark 的改后判据替换冻结用例；
    覆盖只作用于本次重判，不改服务器 config.yaml。
    """
    payload = payload or RejudgeRequest()
    source = _get_run_or_404(session, run_id)
    if source.status != "success":
        raise HTTPException(status_code=400, detail="仅可对成功的评测重判")
    out_dir = _source_out_dir(source)
    if out_dir is None or not (out_dir / "report.json").is_file():
        raise HTTPException(
            status_code=400, detail="源 run 缺 report.json（产物已清理），无法重判"
        )
    # n_runs>1 必须有留痕才能重做 majority；缺失（被治理清理）则拒绝。
    if (source.n_runs or 1) > 1 and not (out_dir / "traces.jsonl.gz").is_file():
        raise HTTPException(
            status_code=400,
            detail="源 run 留痕已被存储治理清理，n_runs>1 无法重做 majority voting",
        )
    if payload.cases_benchmark_id is not None and (
        session.get(Benchmark, payload.cases_benchmark_id) is None
    ):
        raise HTTPException(
            status_code=400,
            detail=f"判据 benchmark {payload.cases_benchmark_id} 不存在",
        )

    # 解析判分模型：选中已保存配置时，由服务端据其构建 judge 覆盖（含 Key，注入运行期）。
    judge_ov = payload.judge
    if payload.judge_model_id is not None:
        jm = session.get(JudgeModelConfig, payload.judge_model_id)
        if jm is None:
            raise HTTPException(
                status_code=404, detail=f"判分模型 {payload.judge_model_id} 不存在"
            )
        base = payload.judge or JudgeOverride()
        judge_ov = JudgeOverride(
            enabled=base.enabled,
            provider=jm.provider or None,
            model=jm.model or None,
            base_url=jm.base_url or None,
            api_version=jm.api_version or None,
            api_key=jm.api_key or None,
            temperature=jm.temperature,
        )

    # 只重判上线失败用例：源 run 须确有 release_passed=false 用例，否则无可重判。
    if payload.only_release_failed:
        failed_n = session.execute(
            select(func.count())
            .select_from(CaseResultRow)
            .where(
                CaseResultRow.run_id == source.id,
                CaseResultRow.release_passed.is_(False),
            )
        ).scalar_one()
        if not failed_n:
            raise HTTPException(
                status_code=400, detail="该评测没有上线失败的用例，无需只重判失败"
            )

    extra_judge = judge_ov.public_dict() if judge_ov else None
    new_name_source = _create_derived_run(
        session, source, suffix="重判", extra_judge_overrides=extra_judge
    )
    new_id = new_name_source.id
    job = build_rejudge_job(
        new_id,
        source_run_id=source.id,
        run_name=new_name_source.name,
        judge_override=judge_ov.model_dump(exclude_none=True) if judge_ov else None,
        cases_benchmark_id=payload.cases_benchmark_id,
        only_release_failed=payload.only_release_failed,
    )
    await get_job_runner().submit(new_id, job)
    return session.get(EvalRun, new_id)


@router.post("/{run_id}/resume", response_model=RunSummaryOut, status_code=201)
async def resume_run(
    run_id: int, session: Session = Depends(get_session)
) -> EvalRun:
    """断点续跑：复用源 run 成功留痕，仅对失败/缺失用例重调 bot，产出新 run。"""
    source = _get_run_or_404(session, run_id)
    if source.status in ("running", "pending"):
        raise HTTPException(status_code=400, detail="运行中或等待中的评测不可续跑")
    out_dir = _source_out_dir(source)
    if out_dir is None:
        raise HTTPException(status_code=400, detail="源 run 产物目录缺失，无法续跑")
    # 可续跑判据：存在可复用留痕（gz 或 partial）即可——支持续跑被服务重启中断、
    # 从未写出 report.json 的 run（其 traces.partial.jsonl 仍在）。
    has_report = (out_dir / "report.json").is_file()
    has_traces = (out_dir / trace_store.TRACES_GZ).is_file() or (
        out_dir / trace_store.PARTIAL
    ).is_file()
    if not has_traces and not has_report:
        raise HTTPException(
            status_code=400,
            detail="源 run 无可复用留痕（从未落盘或已被存储治理清理），无法续跑",
        )
    if not has_report and source.benchmark_id is None:
        raise HTTPException(
            status_code=400, detail="源 run 未关联 benchmark，无法重建用例集续跑"
        )

    derived = _create_derived_run(session, source, suffix="续跑")
    new_id = derived.id
    job = build_resume_job(new_id, source_run_id=source.id, run_name=derived.name)
    await get_job_runner().submit(new_id, job)
    return session.get(EvalRun, new_id)


@router.patch("/{run_id}", response_model=RunSummaryOut)
def rename_run(
    run_id: int,
    payload: RunRenameRequest,
    session: Session = Depends(get_session),
) -> EvalRun:
    """评测改名：空名 422、与其它 run 重名 409、未知 404；与自身同名允许。"""
    run = _get_run_or_404(session, run_id)
    new_name = (payload.name or "").strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="评测名称不能为空")
    dup = session.execute(
        select(EvalRun.id).where(EvalRun.name == new_name, EvalRun.id != run_id)
    ).first()
    if dup is not None:
        raise HTTPException(
            status_code=409, detail=f"评测名称「{new_name}」已存在，请换一个名称"
        )
    run.name = new_name
    return run


@router.post("/{run_id}/pin")
def pin_run(
    run_id: int,
    pinned: bool = Query(..., description="true=置顶保护，false=取消"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """切换置顶保护：免于存储治理清理。同步落/删 KEEP 哨兵，使 CLI/平台共用豁免信号。"""
    run = _get_run_or_404(session, run_id)
    run.pinned = pinned
    out_dir = _source_out_dir(run)
    if out_dir is not None and out_dir.is_dir():
        sentinel = out_dir / retention.KEEP_SENTINEL
        try:
            if pinned:
                sentinel.touch()
            elif sentinel.exists():
                sentinel.unlink()
        except OSError:
            pass
    return {"id": run_id, "pinned": pinned}


@router.get("/{run_id}/progress", response_model=ProgressOut)
def get_progress(run_id: int, session: Session = Depends(get_session)) -> ProgressOut:
    run = _get_run_or_404(session, run_id)
    snap = get_job_runner().progress_snapshot(run_id)
    return ProgressOut(status=run.status, progress=snap)


def _case_n_turns(row: CaseResultRow) -> int:
    """从已落库 detail_json 推导对话轮数（用例 user 轮数，回退 trace user 消息数）。"""
    detail = row.detail_json or {}
    case = detail.get("case") or {}
    turns = case.get("turns") or []
    n = sum(1 for t in turns if isinstance(t, dict) and t.get("role") == "user")
    if n:
        return n
    msgs = ((detail.get("trace") or {}).get("messages")) or []
    n = sum(1 for m in msgs if isinstance(m, dict) and m.get("role") == "user")
    return n or 1


def _case_trace_url(row: CaseResultRow) -> Optional[str]:
    """从已落库 detail_json 取该用例代表 trace 的 Langfuse 深链（无则 None）。

    旧 run 的 detail_json 不含该字段 → 安全回退 None（前端隐藏入口）。
    """
    detail = row.detail_json or {}
    url = ((detail.get("trace") or {}).get("langfuse_trace_url"))
    return url if isinstance(url, str) and url else None


def _guideline_counts(row: CaseResultRow) -> Optional[tuple[int, int]]:
    """从已落 detail_json 派生指南匹配（命中数, 总数）。无带指南锚点得分点时返回 None。

    口径同内核 ``compute_guideline_match_rate`` / 前端用例详情：命中=该带锚点得分点的
    per-point verdict（``scoring_point.point{i}``）``passed``。零迁移、对历史 run 同样生效。
    """
    detail = row.detail_json or {}
    points = (detail.get("case") or {}).get("scoring_points") or []
    anchored = [
        i for i, sp in enumerate(points) if isinstance(sp, dict) and sp.get("guideline")
    ]
    if not anchored:
        return None
    passed_by_idx: dict[int, bool] = {}
    prefix = "scoring_point.point"
    for v in detail.get("verdicts") or []:
        name = v.get("name", "") if isinstance(v, dict) else ""
        if name.startswith(prefix):
            try:
                idx = int(name[len(prefix):])
            except ValueError:
                continue
            passed_by_idx[idx] = bool(v.get("passed"))
    matched = sum(1 for i in anchored if passed_by_idx.get(i, False))
    return matched, len(anchored)


def _filtered_case_rows(
    session: Session,
    run_id: int,
    *,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    score_profile: Optional[str] = None,
    turns: Optional[str] = None,
    guideline: Optional[str] = None,
) -> list[CaseResultRow]:
    stmt = select(CaseResultRow).where(CaseResultRow.run_id == run_id)
    if level:
        stmt = stmt.where(CaseResultRow.level == level)
    if release_passed is not None:
        stmt = stmt.where(CaseResultRow.release_passed == release_passed)
    if stability:
        stmt = stmt.where(CaseResultRow.stability == stability)
    if scenario:
        stmt = stmt.where(CaseResultRow.scenario == scenario)
    # 指南匹配率过滤：full=匹配率为 1.0；partial=非空且 <1；none=匹配率为空（无指南锚点得分点）。
    if guideline == "full":
        stmt = stmt.where(CaseResultRow.guideline_match_rate >= 0.999)
    elif guideline == "partial":
        stmt = stmt.where(
            CaseResultRow.guideline_match_rate.is_not(None),
            CaseResultRow.guideline_match_rate < 0.999,
        )
    elif guideline == "none":
        stmt = stmt.where(CaseResultRow.guideline_match_rate.is_(None))
    stmt = stmt.order_by(CaseResultRow.sample_id)
    rows = list(session.execute(stmt).scalars().all())
    if score_profile:
        rows = [r for r in rows if r.score_profile == score_profile]
    # 对话轮数由 detail_json 推导（无 DB 列）：先标注 n_turns，再按 single/multi 过滤。
    # Langfuse 深链同样从 detail_json 派生（无需 DB 列 / 迁移），旧 run 安全回退 None。
    for r in rows:
        r.n_turns = _case_n_turns(r)
        r.langfuse_trace_url = _case_trace_url(r)
        gc = _guideline_counts(r)
        r.guideline_matched = gc[0] if gc else None
        r.guideline_total = gc[1] if gc else None
    if turns == "single":
        rows = [r for r in rows if r.n_turns <= 1]
    elif turns == "multi":
        rows = [r for r in rows if r.n_turns > 1]
    return rows


@router.get("/{run_id}/cases", response_model=list[CaseRowOut])
def list_case_results(
    run_id: int,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    score_profile: Optional[str] = None,
    turns: Optional[str] = None,
    guideline: Optional[str] = None,
    session: Session = Depends(get_session),
) -> list[CaseResultRow]:
    _get_run_or_404(session, run_id)
    rows = _filtered_case_rows(
        session,
        run_id,
        level=level,
        release_passed=release_passed,
        stability=stability,
        scenario=scenario,
        score_profile=score_profile,
        turns=turns,
        guideline=guideline,
    )
    _attach_review_summary(session, run_id, rows)
    return rows


def _attach_review_summary(
    session: Session, run_id: int, rows: list[CaseResultRow]
) -> None:
    """给每行附最新一条人审裁定摘要（旁路、只读）；无裁定置 None。"""
    by_sample: dict[str, list[CaseAnnotation]] = {}
    for a in session.execute(
        select(CaseAnnotation).where(CaseAnnotation.run_id == run_id)
        .order_by(CaseAnnotation.created_at)
    ).scalars().all():
        by_sample.setdefault(a.sample_id, []).append(a)
    for row in rows:
        anns = by_sample.get(row.sample_id)
        if anns:
            latest = anns[-1]
            row.review = ReviewSummary(
                verdict=latest.verdict,
                reviewer=latest.reviewer,
                suggestion=latest.suggestion,
                comment=latest.comment,
                count=len(anns),
            )
        else:
            row.review = None


@router.get("/{run_id}/cases-yaml", response_model=CasesYamlOut)
def get_cases_yaml(
    run_id: int,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    score_profile: Optional[str] = None,
    guideline: Optional[str] = None,
    sample_id: Optional[str] = None,
    session: Session = Depends(get_session),
) -> CasesYamlOut:
    """导出当前过滤命中用例在其 benchmark 中的完整 YAML，供在线判据编辑器预填。

    传 ``sample_id`` 时只导出该单条用例（供用例明细页就地编辑）；该用例不在过滤命中集时 400。
    """
    run = _get_run_or_404(session, run_id)
    if run.benchmark_id is None:
        raise HTTPException(status_code=400, detail="该评测未关联 benchmark，无法导出用例 YAML")
    bm = session.get(Benchmark, run.benchmark_id)
    if bm is None:
        raise HTTPException(status_code=400, detail="该评测关联的 benchmark 已不存在")

    rows = _filtered_case_rows(
        session, run_id, level=level, release_passed=release_passed,
        stability=stability, scenario=scenario, score_profile=score_profile, guideline=guideline,
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


@router.post("/{run_id}/export-transcripts")
def export_transcripts(
    run_id: int,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    score_profile: Optional[str] = None,
    guideline: Optional[str] = None,
    parent_folder_token: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """按过滤条件导出用例对话流水 Excel，上传飞书并返回链接（以报告名称命名）。

    上传身份：
    - 已登录（飞书 SSO）→ 以当前用户的 user_access_token 直接调飞书 OpenAPI 上传导入；
    - 未登录（本地未配密钥的 dev 模式）→ 回退走 lark-cli 共享身份。

    parent_folder_token：目标飞书文件夹 token；
    - 传非空字符串 → 上传到该文件夹（需该身份对其有写权限）
    - 传空字符串 "" → 上传到个人空间根目录
    - 不传（None）→ 回退使用 config.yaml 的 reporter.lark.parent_folder_token
    """
    run = _get_run_or_404(session, run_id)
    rows = _filtered_case_rows(
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

    settings = get_settings()
    try:
        out_dir = safe_join(settings.outputs_dir, run.run_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法的 run 目录") from exc
    xlsx_path = out_dir / f"{run.run_slug}_transcripts.xlsx"
    write_transcripts_xlsx(report, xlsx_path)

    # token 优先级：调用方动态传入（含空串=根目录）> config.yaml 的回退值。
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
        # 已登录：以当前用户飞书身份上传导入。
        try:
            ensure_fresh_token(session, current_user, get_settings())
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

    # 未登录（dev 未配密钥）：回退 lark-cli 共享身份。
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


@router.get("/{run_id}/cases/{sample_id}")
def get_case_detail(
    run_id: int, sample_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    row = session.execute(
        select(CaseResultRow).where(
            CaseResultRow.run_id == run_id, CaseResultRow.sample_id == sample_id
        )
    ).scalars().first()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"run {run_id} 中无用例 {sample_id}"
        )
    return row.detail_json


def _case_scores(d: dict[str, Any]) -> CaseScores:
    """从一份 CaseResult 的 dict（detail_json 或新结果 dump）抽取判分快照，供前后对比。"""
    d = d or {}
    return CaseScores(
        hard_gate_passed=bool(d.get("hard_gate_passed")),
        gate_passed=bool(d.get("gate_passed")),
        release_passed=bool(d.get("release_passed")),
        composite_score=d.get("composite_score"),
        grade=d.get("grade") or "",
        dimension_scores=d.get("dimension_scores") or {},
        dimension_max=d.get("dimension_max") or {},
        score_profile=d.get("score_profile") or "",
        score_deductions=d.get("score_deductions") or [],
        failure_tags=d.get("failure_tags") or [],
        needs_human_review=bool(d.get("needs_human_review")),
        verdicts=[
            {
                "name": v.get("name"),
                "passed": v.get("passed"),
                "score": v.get("score"),
                "max_score": v.get("max_score"),
                "reason": v.get("reason"),
            }
            for v in (d.get("verdicts") or [])
        ],
    )


def _override_from_yaml(yaml_text: str, sample_id: str) -> dict[str, Any]:
    """从单条/多条用例 YAML 抽取指定 sample_id 的 4 个判据字段（用例明细试判用）。"""
    try:
        docs = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=422, detail=f"YAML 解析失败：{exc}") from exc
    items = docs if isinstance(docs, list) else [docs]
    for it in items:
        if isinstance(it, dict) and it.get("sample_id") == sample_id:
            ov: dict[str, Any] = {"sample_id": sample_id}
            for f in ("expected_behavior", "hard_gates", "rubric", "scoring_points"):
                if it.get(f) is not None:
                    ov[f] = it[f]
            return ov
    raise HTTPException(status_code=400, detail=f"YAML 中未找到用例 {sample_id}")


@router.post(
    "/{run_id}/cases/{sample_id}/preview-rejudge",
    response_model=PreviewRejudgeResponse,
)
async def preview_rejudge_case_route(
    run_id: int,
    sample_id: str,
    payload: Optional[PreviewRejudgeRequest] = Body(default=None),
    session: Session = Depends(get_session),
) -> PreviewRejudgeResponse:
    """单用例 ephemeral 试判预览：用编辑后判据 + 该用例冻结留痕重算，返回新判定与 diff。

    纯只读旁路：MUST NOT 写库、新建 run、复制留痕、改当前 run 判分或写 case_annotation。
    """
    payload = payload or PreviewRejudgeRequest()
    source = _get_run_or_404(session, run_id)
    row = _case_row_or_404(session, run_id, sample_id)
    if source.status != "success":
        raise HTTPException(status_code=400, detail="仅可对成功的评测试判")
    out_dir = _source_out_dir(source)
    if out_dir is None or not (out_dir / "report.json").is_file():
        raise HTTPException(
            status_code=400, detail="源 run 缺 report.json（产物已清理），无法试判"
        )
    if (source.n_runs or 1) > 1 and not (out_dir / "traces.jsonl.gz").is_file():
        raise HTTPException(
            status_code=400,
            detail="源 run 留痕已被存储治理清理，n_runs>1 无法试判",
        )

    if payload.case_override is not None:
        override = payload.case_override.model_dump(exclude_none=True)
    elif payload.yaml_text:
        override = _override_from_yaml(payload.yaml_text, sample_id)
    else:
        override = None
    try:
        new_result = await preview_rejudge_case(
            source_run_id=run_id, sample_id=sample_id, case_override=override
        )
    except BenchmarkValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    current = _case_scores(row.detail_json)
    preview = _case_scores(new_result.model_dump(mode="json"))
    return PreviewRejudgeResponse(
        sample_id=sample_id,
        current=current,
        preview=preview,
        changed=current != preview,
        case_result=new_result.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# 人工审核队列（HITL）：旁路记录，永不回写判分


def _is_red_flag(row: CaseResultRow) -> bool:
    triage = (
        ((row.detail_json or {}).get("case") or {}).get("hard_gates") or {}
    ).get("red_flag_triage")
    return bool(triage) and triage != "none"


def _queue_reasons(row: CaseResultRow) -> list[str]:
    """该用例的入队原因（空=不入队）。"""
    reasons: list[str] = []
    if row.needs_human_review:
        reasons.append("needs_human_review")
    if not row.release_passed:
        reasons.append("release_failed")  # 所有上线判定失败均入队
        if _is_red_flag(row):
            reasons.append("red_flag_failed")  # 红旗失败：更具体的高危标注
    if getattr(row, "review_requested", False):
        reasons.append("manual")
    return reasons


def _case_row_or_404(session: Session, run_id: int, sample_id: str) -> CaseResultRow:
    row = session.execute(
        select(CaseResultRow).where(
            CaseResultRow.run_id == run_id, CaseResultRow.sample_id == sample_id
        )
    ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} 中无用例 {sample_id}")
    return row


@router.get("/{run_id}/review-queue", response_model=list[ReviewQueueItemOut])
def get_review_queue(
    run_id: int,
    level: Optional[str] = None,
    release_passed: Optional[bool] = None,
    stability: Optional[str] = None,
    scenario: Optional[str] = None,
    score_profile: Optional[str] = None,
    session: Session = Depends(get_session),
) -> list[ReviewQueueItemOut]:
    """返回该 run 入队（needs_human_review / 红旗失败 / 手动加入）的用例及其裁定状态。"""
    _get_run_or_404(session, run_id)
    rows = _filtered_case_rows(
        session, run_id, level=level, release_passed=release_passed,
        stability=stability, scenario=scenario, score_profile=score_profile,
    )
    anns_by_sample: dict[str, list[CaseAnnotation]] = {}
    for a in session.execute(
        select(CaseAnnotation).where(CaseAnnotation.run_id == run_id)
        .order_by(CaseAnnotation.created_at)
    ).scalars().all():
        anns_by_sample.setdefault(a.sample_id, []).append(a)

    items: list[ReviewQueueItemOut] = []
    for r in rows:
        reasons = _queue_reasons(r)
        if not reasons:
            continue
        anns = anns_by_sample.get(r.sample_id, [])
        items.append(ReviewQueueItemOut(
            sample_id=r.sample_id, scenario=r.scenario, level=r.level,
            release_passed=r.release_passed, composite_score=r.composite_score,
            failure_tags=list(r.failure_tags or []), reasons=reasons,
            reviewed=bool(anns),
            annotations=[AnnotationOut.model_validate(a) for a in anns],
        ))
    return items


@router.get(
    "/{run_id}/cases/{sample_id}/annotations",
    response_model=list[AnnotationOut],
)
def get_case_annotations(
    run_id: int, sample_id: str, session: Session = Depends(get_session)
) -> list[CaseAnnotation]:
    """该用例的全部人工裁定（按时间）。"""
    return list(session.execute(
        select(CaseAnnotation).where(
            CaseAnnotation.run_id == run_id, CaseAnnotation.sample_id == sample_id
        ).order_by(CaseAnnotation.created_at)
    ).scalars().all())


@router.post("/{run_id}/cases/{sample_id}/request-review")
def request_review(
    run_id: int, sample_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """手动把用例加入审核队列（幂等）。"""
    row = _case_row_or_404(session, run_id, sample_id)
    row.review_requested = True
    return {"run_id": run_id, "sample_id": sample_id, "review_requested": True}


@router.post(
    "/{run_id}/cases/{sample_id}/annotate",
    response_model=AnnotationOut,
    status_code=201,
)
def annotate_case(
    run_id: int,
    sample_id: str,
    payload: AnnotateRequest,
    session: Session = Depends(get_session),
    current_user: Optional[FeishuUser] = Depends(get_current_user_optional),
) -> CaseAnnotation:
    """记录一条人工裁定（agree/override）。MUST NOT 改动任何判分字段。"""
    _case_row_or_404(session, run_id, sample_id)
    ann = CaseAnnotation(
        run_id=run_id,
        sample_id=sample_id,
        reviewer=current_user.name if current_user else None,
        verdict=payload.verdict,
        suggestion=payload.suggestion,
        comment=payload.comment,
    )
    session.add(ann)
    session.flush()
    return ann


@router.get("/{run_id}/review-stats", response_model=ReviewStatsOut)
def get_review_stats(
    run_id: int, session: Session = Depends(get_session)
) -> ReviewStatsOut:
    """队列计数与人审通过率/分歧率（按每条用例最新裁定口径）。"""
    _get_run_or_404(session, run_id)
    rows = _filtered_case_rows(session, run_id)
    queued = [r.sample_id for r in rows if _queue_reasons(r)]
    queue_total = len(queued)

    latest: dict[str, str] = {}
    for a in session.execute(
        select(CaseAnnotation).where(CaseAnnotation.run_id == run_id)
        .order_by(CaseAnnotation.created_at)
    ).scalars().all():
        if a.sample_id in queued:
            latest[a.sample_id] = a.verdict  # 后写覆盖 → 最新裁定

    reviewed = len(latest)
    agree = sum(1 for v in latest.values() if v == "agree")
    override = sum(1 for v in latest.values() if v == "override")
    return ReviewStatsOut(
        queue_total=queue_total,
        reviewed=reviewed,
        pending=queue_total - reviewed,
        agree=agree,
        override=override,
        agree_rate=(agree / reviewed) if reviewed else 0.0,
        disagree_rate=(override / reviewed) if reviewed else 0.0,
    )


@router.get("/{run_id}/diff")
def diff_run(
    run_id: int,
    against: int = Query(..., description="对比的历史 run id"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    current = _get_run_or_404(session, run_id)
    base = session.get(EvalRun, against)
    if base is None:
        raise HTTPException(status_code=404, detail=f"对比目标 run {against} 不存在")
    return compare_runs(session, current, base)
