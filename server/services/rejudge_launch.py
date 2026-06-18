"""重判 / 试判：HTTP 层以下的校验与派生 run 编排（job 执行在 eval_rejudge）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from medeval import trace_store

from ..models_db import Benchmark, CaseResultRow, EvalRun, JudgeModelConfig
from ..schemas import (
    JudgeOverride,
    PreviewRejudgeRequest,
    PreviewRejudgeResponse,
    RejudgeRequest,
)
from .case_query import case_row_or_404, case_scores, override_from_yaml
from .runs import create_derived_run, get_run_or_404, source_out_dir

if TYPE_CHECKING:
    from ..jobs import JobRunner


class RejudgeLaunchError(Exception):
    """业务校验失败；router 转为 HTTPException。"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def resolve_judge_override(
    session: Session, payload: RejudgeRequest
) -> JudgeOverride | None:
    if payload.judge_model_id is None:
        return payload.judge
    jm = session.get(JudgeModelConfig, payload.judge_model_id)
    if jm is None:
        raise RejudgeLaunchError(404, f"判分模型 {payload.judge_model_id} 不存在")
    base = payload.judge or JudgeOverride()
    return JudgeOverride(
        enabled=base.enabled,
        provider=jm.provider or None,
        model=jm.model or None,
        base_url=jm.base_url or None,
        api_version=jm.api_version or None,
        api_key=jm.api_key or None,
        temperature=jm.temperature,
        prompt_template=jm.prompt_template or None,
    )


def _validate_rejudge_artifacts(source: EvalRun, *, action: str) -> None:
    if source.status != "success":
        raise RejudgeLaunchError(400, f"仅可对成功的评测{action}")
    out_dir = source_out_dir(source)
    if out_dir is None or not (out_dir / "report.json").is_file():
        raise RejudgeLaunchError(400, f"源 run 缺 report.json（产物已清理），无法{action}")
    if (source.n_runs or 1) > 1 and not (out_dir / trace_store.TRACES_GZ).is_file():
        raise RejudgeLaunchError(
            400,
            f"源 run 留痕已被存储治理清理，n_runs>1 无法{action}",
        )


def validate_rejudge_request(session: Session, source: EvalRun, payload: RejudgeRequest) -> None:
    _validate_rejudge_artifacts(source, action="重判")
    if payload.cases_benchmark_id is not None and (
        session.get(Benchmark, payload.cases_benchmark_id) is None
    ):
        raise RejudgeLaunchError(
            400, f"判据 benchmark {payload.cases_benchmark_id} 不存在"
        )
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
            raise RejudgeLaunchError(400, "该评测没有上线失败的用例，无需只重判失败")


def prepare_rejudge_derived_run(
    session: Session, source: EvalRun, payload: RejudgeRequest
) -> tuple[EvalRun, JudgeOverride | None]:
    validate_rejudge_request(session, source, payload)
    judge_ov = resolve_judge_override(session, payload)
    extra_judge = judge_ov.public_dict() if judge_ov else None
    derived = create_derived_run(
        session, source, suffix="重判", extra_judge_overrides=extra_judge
    )
    return derived, judge_ov


async def launch_rejudge_run(
    session: Session,
    source_run_id: int,
    payload: RejudgeRequest,
    *,
    job_runner: "JobRunner",
    build_rejudge_job,
) -> EvalRun:
    """校验源 run → 派生 pending run → 提交重判 job。"""
    source = get_run_or_404(session, source_run_id)
    derived, judge_ov = prepare_rejudge_derived_run(session, source, payload)
    job = build_rejudge_job(
        derived.id,
        source_run_id=source.id,
        run_name=derived.name,
        judge_override=judge_ov.model_dump(exclude_none=True) if judge_ov else None,
        cases_benchmark_id=payload.cases_benchmark_id,
        only_release_failed=payload.only_release_failed,
    )
    await job_runner.submit(derived.id, job)
    return derived


def resolve_preview_case_override(
    payload: PreviewRejudgeRequest, sample_id: str
) -> dict[str, Any] | None:
    if payload.case_override is not None:
        return payload.case_override.model_dump(exclude_none=True)
    if payload.yaml_text:
        return override_from_yaml(payload.yaml_text, sample_id)
    return None


def validate_preview_request(session: Session, run_id: int, sample_id: str) -> EvalRun:
    source = get_run_or_404(session, run_id)
    case_row_or_404(session, run_id, sample_id)
    _validate_rejudge_artifacts(source, action="试判")
    return source


def build_preview_response(row: CaseResultRow, sample_id: str, new_result) -> PreviewRejudgeResponse:
    current = case_scores(row.detail_json)
    preview = case_scores(new_result.model_dump(mode="json"))
    return PreviewRejudgeResponse(
        sample_id=sample_id,
        current=current,
        preview=preview,
        changed=current != preview,
        case_result=new_result.model_dump(mode="json"),
    )
