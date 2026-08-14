"""把数据库中的无密钥任务描述还原为可执行评测闭包。"""

from __future__ import annotations

from typing import Any

from medeval import trace_store

from .db import session_scope
from .models_db import EvalRun, JudgeModelConfig
from .paths import safe_join
from .settings import Settings


def _saved_model_override(model_id: int | None) -> dict[str, Any]:
    if model_id is None:
        return {}
    with session_scope() as session:
        row = session.get(JudgeModelConfig, model_id)
        if row is None:
            raise ValueError(f"模型配置 {model_id} 不存在，任务无法恢复")
        return {
            "provider": row.provider or None,
            "model": row.model or None,
            "base_url": row.base_url or None,
            "api_version": row.api_version or None,
            "api_key": row.api_key or None,
            "temperature": row.temperature,
            "enable_thinking": row.enable_thinking,
        }


def _merge_saved_model(public: dict[str, Any] | None, model_id: int | None) -> dict[str, Any] | None:
    if not public and model_id is None:
        return None
    return {**dict(public or {}), **_saved_model_override(model_id)}


def _evaluation_has_checkpoint(run_id: int, settings: Settings) -> bool:
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        if run is None or not run.run_slug or run.run_slug == "(pending)":
            return False
        try:
            out_dir = safe_join(settings.outputs_dir, run.run_slug)
        except ValueError:
            return False
    return any(
        (out_dir / name).is_file()
        for name in (trace_store.PARTIAL, trace_store.TRACES_GZ, "report.json")
    )


def build_job_from_payload(
    run_id: int,
    kind: str,
    payload: dict[str, Any],
    settings: Settings,
):
    """Worker 的单一反序列化入口；初次评测有断点时自动切换为原地续跑。"""
    if kind == "evaluation":
        if _evaluation_has_checkpoint(run_id, settings):
            from .services.eval_resume import build_resume_job

            with session_scope() as session:
                run = session.get(EvalRun, run_id)
                run_name = run.name if run is not None else payload.get("run_name")
            return build_resume_job(
                run_id,
                source_run_id=run_id,
                run_name=run_name,
                in_place=True,
                settings=settings,
            )
        from .services.eval_launch import build_eval_job

        adapter = dict(payload.get("adapter") or {})
        simulator_id = payload.get("user_simulator_model_id")
        if simulator_id is not None:
            simulator_public = dict(adapter.get("user_simulator") or {})
            adapter["user_simulator"] = _merge_saved_model(simulator_public, simulator_id)
        return build_eval_job(
            run_id,
            benchmark_id=int(payload["benchmark_id"]),
            run_name=payload.get("run_name"),
            levels=list(payload.get("levels") or []),
            limit=int(payload.get("limit") or 0),
            repeat=payload.get("repeat"),
            judge_full=_merge_saved_model(payload.get("judge"), payload.get("judge_model_id")),
            adapter_full=adapter,
            judge_model_id=payload.get("judge_model_id"),
            user_simulator_model_id=simulator_id,
            settings=settings,
        )
    if kind == "resume":
        from .services.eval_resume import build_resume_job

        return build_resume_job(run_id, settings=settings, **payload)
    if kind == "rejudge":
        from .services.eval_rejudge import build_rejudge_job

        values = dict(payload)
        model_id = values.pop("judge_model_id", None)
        values["judge_override"] = _merge_saved_model(
            values.get("judge_override"), model_id
        )
        return build_rejudge_job(run_id, settings=settings, judge_model_id=model_id, **values)
    if kind == "cases_retry":
        from .services.case_retry import build_retry_cases_job

        return build_retry_cases_job(
            run_id,
            sample_ids=list(payload.get("sample_ids") or []),
            settings=settings,
        )
    raise ValueError(f"不支持的持久化任务类型: {kind}")
