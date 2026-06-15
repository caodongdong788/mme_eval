"""评测任务：把网页参数合并进 config → 复用 medeval 编排执行 → 落库 + 双写 outputs。

判分核心零改动：仅把打分模型覆盖合并进 ``config.judges.llm/scoring_point``，被测 bot 覆盖合并进
``config.adapter.openai_compat``，再走现有 ``build_judges`` / ``evaluate``。
模块级导入这些函数，便于测试 monkeypatch。

平台与 CLI 能力对齐：网页发起的评测同样落 ``traces.jsonl.gz``（``run_name/out_dir``）、收尾按
``config.run.retention`` 治理存储；并支持对历史 run 的**离线重判**（``judge_traces``，零 bot 调用）
与**断点续跑**（``evaluate(resume_dir=...)``，复用成功留痕）。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from sqlalchemy import select

from medeval import retention, trace_store
from medeval.adapter import build_adapter
from medeval.config import Config, ThresholdRule, load_config
from medeval.models import CaseResult, RunReport
from medeval.reporter.aggregator import build_report
from medeval.run_slug import make_run_slug
from medeval.service import (
    build_adjudicator,
    build_judges,
    evaluate,
    judge_traces,
    resolve_diff_target,
    write_core_artifacts,
)

from .benchmarks import BenchmarkValidationError, _apply_case_overrides, load_benchmark_cases
from .db import session_scope
from .ingest import finalize_run
from .models_db import Benchmark, EvalRun
from .progress import InMemoryProgress
from .settings import Settings, get_settings

_JUDGE_KEYS = (
    "enabled",
    "provider",
    "model",
    "base_url",
    "api_version",
    "api_key_env",
    "api_key",
    "temperature",
)
_ADAPTER_KEYS = ("model", "base_url", "system_prompt", "api_key_env", "api_key", "temperature")


def _apply_judge_overrides(config: Config, judge: dict[str, Any] | None) -> None:
    if not judge:
        return
    for target in (config.judges.llm, config.judges.scoring_point):
        for k in _JUDGE_KEYS:
            v = judge.get(k)
            if v is not None and hasattr(target, k):
                setattr(target, k, v)


def load_release_threshold_overrides(session) -> dict[str, float]:
    """读取按 profile 的「综合分上线阈值」覆盖（无行=空，表示沿用 config.yaml）。"""
    from .models_db import ReleaseThresholdConfig

    rows = session.execute(select(ReleaseThresholdConfig)).scalars().all()
    return {r.profile: float(r.composite_threshold) for r in rows}


def apply_release_threshold_overrides(
    config: Config, overrides: dict[str, float] | None
) -> None:
    """把按 profile 的综合分上线阈值覆盖注入 config.scoring（仅改综合分阈值，保留原 gates）。

    覆盖语义：对应 profile 的 pass_rule 改为 ``{type: threshold, min_composite: x, gates: 原 gates}``；
    ``default`` 覆盖写顶层 ``scoring.pass_rule``。未覆盖的 profile 原样不动（零行为变化）。
    """
    if not overrides:
        return

    def _gates_of(pr: Any) -> dict[str, Any]:
        # 现有 pass_rule 若是 threshold，沿用其 gates；perfect/缺省则无 gates。
        if isinstance(pr, ThresholdRule):
            return dict(pr.gates)
        return {}

    scoring = config.scoring
    for profile, thr in overrides.items():
        if profile == "default":
            scoring.pass_rule = ThresholdRule(
                min_composite=float(thr), gates=_gates_of(scoring.pass_rule)
            )
        elif profile in scoring.profiles:
            p = scoring.profiles[profile]
            p.pass_rule = ThresholdRule(
                min_composite=float(thr), gates=_gates_of(p.pass_rule)
            )


def _apply_adapter_overrides(config: Config, adapter: dict[str, Any] | None) -> None:
    if not adapter:
        return
    oc = config.adapter.openai_compat
    if oc is None:
        return
    for k in _ADAPTER_KEYS:
        v = adapter.get(k)
        if v is not None and hasattr(oc, k):
            setattr(oc, k, v)


# ---------------------------------------------------------------------------
# 落库 / 产物 / 存储治理（rejudge / resume / 正常评测共用）


def _persist_outcome(
    run_id: int,
    report: RunReport,
    out_dir: Path,
    *,
    prev_json: Path | None,
    parent_run_id: int | None = None,
) -> None:
    """统一收尾：落库（含 has_traces）+ 双写 outputs（diff）。文件失败不影响落库。"""
    has_traces = (out_dir / "traces.jsonl.gz").is_file()
    with session_scope() as session:
        row = session.get(EvalRun, run_id)
        finalize_run(session, row, report)
        row.has_traces = has_traces
        if parent_run_id is not None:
            row.parent_run_id = parent_run_id

    try:
        write_core_artifacts(report, out_dir, prev_json=prev_json)
    except Exception:  # noqa: BLE001 —— 文件产物失败不应使整次评测判失败
        logger.warning("run %s 写 outputs 产物失败（不影响落库）", run_id, exc_info=True)


def _apply_retention(config: Config, settings: Settings) -> None:
    """按 config.run.retention 清理历史 run 胖产物；失败不影响评测。"""
    ret = config.run.retention
    if not getattr(ret, "enabled", True):
        return
    try:
        retention.prune_outputs(
            settings.outputs_dir,
            keep_last=ret.keep_last,
            ttl_days=ret.ttl_days,
            keep_tagged=ret.keep_tagged,
        )
    except Exception:  # noqa: BLE001 —— 治理失败不应使评测判失败
        logger.warning("retention 清理历史产物失败（不影响评测）", exc_info=True)


def _load_source_run(
    settings: Settings, source_run_id: int
) -> tuple[str, int | None, dict[str, Any], dict[str, Any]]:
    """读源 run 的标量元数据（在独立会话里取出即关闭，避免跨 await 持锁）。"""
    with session_scope() as session:
        src = session.get(EvalRun, source_run_id)
        if src is None:
            raise ValueError(f"源 run {source_run_id} 不存在")
        return (
            src.run_slug,
            src.benchmark_id,
            dict(src.judge_overrides or {}),
            dict(src.adapter_overrides or {}),
        )


def _frozen_cases_and_traces(src_dir: Path, *, require_traces: bool):
    """从源 run 目录重建（冻结用例, per_case_traces, n_runs）。"""
    report_json = src_dir / "report.json"
    if not report_json.is_file():
        raise ValueError(f"源 run 缺 {report_json.name}，无法重判/续跑")
    prev = RunReport.model_validate_json(report_json.read_text(encoding="utf-8"))
    cases = [r.case for r in prev.results]
    if not cases:
        raise ValueError("源 run 无用例结果")
    n_runs = prev.n_runs or 1

    bundle = trace_store.read_traces(src_dir)
    if bundle is not None:
        per_case_traces = bundle.per_case_traces(cases, n_runs)
    elif require_traces and n_runs > 1:
        raise ValueError(
            f"源 run 缺 traces.jsonl.gz 且 n_runs={n_runs}>1，留痕不足以重做 majority voting"
        )
    else:
        # n_runs==1 回退用 report.json 的代表性 trace（或重判路径无强约束）。
        per_case_traces = [[r.trace] for r in prev.results]
    return cases, per_case_traces, n_runs


# ---------------------------------------------------------------------------
# run 计划（plan.json）：捕获过滤后的实际用例集，使中断后仍可精确重建意图用例集

PLAN = "plan.json"


def _write_run_plan(out_dir: Path, cases: list[Any], n_runs: int) -> None:
    """落 ``plan.json``（``{sample_ids, n_runs}``）。失败不阻塞评测（best-effort）。"""
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / PLAN).write_text(
            json.dumps(
                {"sample_ids": [c.sample_id for c in cases], "n_runs": int(n_runs)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001 —— plan 落盘失败不应使评测失败
        pass


def _read_run_plan(out_dir: Path) -> dict[str, Any] | None:
    """读 ``plan.json``，缺失 / 损坏时返回 None。"""
    try:
        p = out_dir / PLAN
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return None


def _resume_cases_and_traces(src_dir: Path, settings: Settings, bm_id: int | None):
    """续跑用例集重建：有 report.json 取冻结用例；否则从 benchmark + plan.json 重建。

    支持续跑**被服务重启 / 崩溃中断、从未写出 report.json** 的 run：此时从源 run 关联的
    benchmark 重建用例集（按 ``plan.json`` 的 sample_ids 过滤 / 排序，缺 plan 则回退全量），
    再以 ``traces.partial.jsonl`` 中成功留痕续跑。
    """
    if (src_dir / "report.json").is_file():
        return _frozen_cases_and_traces(src_dir, require_traces=False)

    bundle = trace_store.read_traces(src_dir)
    if bundle is None:
        raise ValueError("源 run 既无 report.json 也无可复用留痕，无法续跑")
    if bm_id is None:
        raise ValueError("源 run 未关联 benchmark，无法重建用例集续跑")

    with session_scope() as session:
        bm = session.get(Benchmark, bm_id)
        if bm is None:
            raise ValueError(f"源 run 的 benchmark {bm_id} 已不存在，无法续跑")
        all_cases = load_benchmark_cases(bm, settings=settings)

    plan = _read_run_plan(src_dir)
    if plan and plan.get("sample_ids"):
        order = {sid: i for i, sid in enumerate(plan["sample_ids"])}
        cases = sorted(
            [c for c in all_cases if c.sample_id in order],
            key=lambda c: order[c.sample_id],
        )
    else:
        cases = list(all_cases)

    n_runs = int((plan or {}).get("n_runs") or bundle.meta.get("n_runs") or 1)
    per_case_traces = bundle.per_case_traces(cases, n_runs)
    return cases, per_case_traces, n_runs


# ---------------------------------------------------------------------------
# 正常评测


def build_eval_job(
    run_id: int,
    *,
    benchmark_id: int,
    run_name: str | None = None,
    score_profiles: list[str] | None = None,
    levels: list[str] | None = None,
    limit: int = 0,
    repeat: int | None = None,
    judge_full: dict[str, Any] | None = None,
    adapter_full: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> Callable[[InMemoryProgress], Awaitable[None]]:
    """构造一个评测 JobFn（供 JobRunner.submit）。"""
    settings = settings or get_settings()
    score_profiles = score_profiles or []
    levels = levels or []

    async def job(progress: InMemoryProgress) -> None:
        config = load_config(settings.config_path)
        if run_name:
            config.run.name = run_name
        if score_profiles:
            config.cases.score_profiles = list(score_profiles)
        if repeat:
            config.run.repeat = repeat
        _apply_judge_overrides(config, judge_full)
        _apply_adapter_overrides(config, adapter_full)

        with session_scope() as session:
            bm = session.get(Benchmark, benchmark_id)
            if bm is None:
                raise ValueError(f"benchmark {benchmark_id} 不存在")
            cases = load_benchmark_cases(
                bm, score_profiles=score_profiles or None, settings=settings
            )
            # 按 profile 的「综合分上线阈值」覆盖：仅作用于本次新评测，进入 config_snapshot。
            apply_release_threshold_overrides(
                config, load_release_threshold_overrides(session)
            )
        if levels:
            level_set = set(levels)
            cases = [c for c in cases if getattr(c.level, "value", c.level) in level_set]
        if limit:
            cases = cases[:limit]

        adapter = build_adapter(config.adapter.type, config.adapter.model_dump())
        judges = build_judges(config.judges)
        adjudicator = build_adjudicator(config.judges)

        # 提前定 run_slug / out_dir，使网页评测与 CLI 一样落会话留痕（traces.jsonl.gz）。
        run_slug = make_run_slug(config.run.name)
        out_dir = settings.outputs_dir / run_slug
        # 落 plan.json（过滤后的实际用例集），使本 run 中断后仍可精确续跑。
        _write_run_plan(out_dir, cases, config.run.repeat or 1)

        report = await evaluate(
            config,
            cases,
            adapter,
            judges,
            adjudicator,
            progress=progress,
            run_name=run_slug,
            out_dir=out_dir,
        )

        prev = resolve_diff_target("auto", settings.outputs_dir, out_dir)
        _persist_outcome(run_id, report, out_dir, prev_json=prev)
        _apply_retention(config, settings)

    return job


# ---------------------------------------------------------------------------
# 离线重判：对源 run 冻结用例 + 冻结留痕仅重跑判分（零 bot 调用）


def build_rejudge_job(
    run_id: int,
    *,
    source_run_id: int,
    run_name: str | None = None,
    judge_override: dict[str, Any] | None = None,
    cases_benchmark_id: int | None = None,
    only_release_failed: bool = False,
    settings: Settings | None = None,
) -> Callable[[InMemoryProgress], Awaitable[None]]:
    """离线重判，可选临时覆盖 judge 模型 / 用某 benchmark 的改后判据替换冻结用例。

    覆盖只作用于本次重判，bot 会话留痕始终冻结。``only_release_failed=True`` 时只对源 run
    上线判定失败（``release_passed=false``）的用例重判，通过用例沿用源结果，合并后整体重算。
    """
    settings = settings or get_settings()

    async def job(progress: InMemoryProgress) -> None:
        src_slug, _bm_id, judge_ov, adapter_ov = _load_source_run(settings, source_run_id)
        src_dir = settings.outputs_dir / src_slug
        cases, per_case_traces, n_runs = _frozen_cases_and_traces(
            src_dir, require_traces=True
        )

        # 用某 benchmark 的改后判据按 sample_id 替换冻结用例（trace 仍按原顺序配对）。
        if cases_benchmark_id is not None:
            with session_scope() as session:
                bm = session.get(Benchmark, cases_benchmark_id)
                if bm is None:
                    raise ValueError(f"判据 benchmark {cases_benchmark_id} 不存在")
                override_cases = load_benchmark_cases(bm, settings=settings)
            ov_by_id = {c.sample_id: c for c in override_cases}
            cases = [ov_by_id.get(c.sample_id, c) for c in cases]

        config = load_config(settings.config_path)
        if run_name:
            config.run.name = run_name
        config.run.repeat = n_runs
        # 先沿用源 run 的 judge/bot 身份，再叠加本次覆盖（覆盖优先），让变化成为单变量。
        _apply_judge_overrides(config, judge_ov)
        _apply_adapter_overrides(config, adapter_ov)
        _apply_judge_overrides(config, judge_override)
        # 重判也套用当前「综合分上线阈值」覆盖（与新评测一致），进入新 run 的 config_snapshot。
        with session_scope() as session:
            apply_release_threshold_overrides(
                config, load_release_threshold_overrides(session)
            )

        judges = build_judges(config.judges)
        adjudicator = build_adjudicator(config.judges)

        new_slug = make_run_slug(config.run.name)
        out_dir = settings.outputs_dir / new_slug

        src_bundle = trace_store.read_traces(src_dir)
        src_fp = src_bundle.meta.get("adapter_fingerprint", "") if src_bundle else ""

        if only_release_failed:
            # 只重判源 run 上线失败用例：判失败子集 → 与源报告通过用例合并 → 整体重算。
            src_report = RunReport.model_validate_json(
                (src_dir / "report.json").read_text(encoding="utf-8")
            )
            failed_ids = {
                r.case.sample_id for r in src_report.results if not r.release_passed
            }
            if not failed_ids:
                raise ValueError("源 run 无上线失败用例，无法只重判失败")
            sub_cases = []
            sub_traces = []
            for c, t in zip(cases, per_case_traces):
                if c.sample_id in failed_ids:
                    sub_cases.append(c)
                    sub_traces.append(t)
            partial = await judge_traces(
                config,
                sub_cases,
                sub_traces,
                judges,
                adjudicator,
                progress=progress,
                run_name=new_slug,
                declare_plan=True,
            )
            new_by_id = {r.case.sample_id: r for r in partial.results}
            # 按源 run 用例顺序合并：失败用例用新结果，其余沿用源结果。
            merged = [
                new_by_id.get(r.case.sample_id, r)
                if r.case.sample_id in failed_ids
                else r
                for r in src_report.results
            ]
            report = build_report(
                run_name=new_slug,
                results=merged,
                adapter_type=config.adapter.type,
                config_snapshot=config.model_dump(mode="json"),
                description=config.run.description,
                n_runs=n_runs,
            )
        else:
            report = await judge_traces(
                config,
                cases,
                per_case_traces,
                judges,
                adjudicator,
                progress=progress,
                run_name=new_slug,
                declare_plan=True,
            )

        # 把冻结留痕复制进新目录，使新 run 仍可再次被重判 / 续跑。
        try:
            trace_store.write_traces(
                out_dir,
                cases,
                per_case_traces,
                store_raw=config.run.store_raw,
                meta={
                    "schema": trace_store.SCHEMA_VERSION,
                    "adapter_fingerprint": src_fp,
                    "store_raw": config.run.store_raw,
                    "n_runs": n_runs,
                    "n_cases": len(cases),
                    "rejudged_from": src_slug,
                },
            )
        except Exception:  # noqa: BLE001 —— 留痕复制失败不影响重判结果落库
            pass

        # 默认与源 run 对比，凸显「判分逻辑变化」这一单变量。
        _persist_outcome(
            run_id,
            report,
            out_dir,
            prev_json=src_dir / "report.json",
            parent_run_id=source_run_id,
        )
        _apply_retention(config, settings)

    return job


# ---------------------------------------------------------------------------
# 单用例 ephemeral 试判预览：取该用例冻结留痕 + 套用判据覆盖，仅重跑判分重算评分。
# 零落库、零 run 目录、零留痕复制、零 bot 调用——纯只读旁路，供人审就地验证判据。


async def preview_rejudge_case(
    *,
    source_run_id: int,
    sample_id: str,
    case_override: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> CaseResult:
    """对源 run 某用例做一次性试判：用编辑后的判据 + 该用例冻结留痕重跑判分并重算评分。

    判分口径与正式重判一致（沿用源 run 的 judge/bot 身份 + 当前综合分阈值覆盖，经 ``judge_traces``）。
    **不写任何库、不新建 run/产物目录、不复制留痕、不调用被测 bot。** 返回重算后的单条
    ``CaseResult``（仅供展示，不持久化）。

    用例不在源 run、或留痕不足（n_runs>1 且留痕已清理）时抛 ``ValueError``；判据非法抛
    ``BenchmarkValidationError``。
    """
    settings = settings or get_settings()
    src_slug, _bm_id, judge_ov, adapter_ov = _load_source_run(settings, source_run_id)
    src_dir = settings.outputs_dir / src_slug
    cases, per_case_traces, n_runs = _frozen_cases_and_traces(src_dir, require_traces=True)

    idx = next((i for i, c in enumerate(cases) if c.sample_id == sample_id), None)
    if idx is None:
        raise ValueError(f"用例 {sample_id} 不在源 run 的结果中")
    sub_cases = [cases[idx]]
    sub_traces = [per_case_traces[idx]]

    # 套用判据覆盖（仅 4 个判据字段，按 sample_id），合并语义与 benchmark 派生一致。
    if case_override:
        ov = dict(case_override)
        ov["sample_id"] = sample_id
        sub_cases = _apply_case_overrides(sub_cases, [ov])

    config = load_config(settings.config_path)
    config.run.repeat = n_runs
    # 沿用源 run 的 judge/bot 身份，再套当前综合分阈值覆盖（与正式重判口径一致）。
    _apply_judge_overrides(config, judge_ov)
    _apply_adapter_overrides(config, adapter_ov)
    with session_scope() as session:
        apply_release_threshold_overrides(
            config, load_release_threshold_overrides(session)
        )

    judges = build_judges(config.judges)
    adjudicator = build_adjudicator(config.judges)
    report = await judge_traces(
        config,
        sub_cases,
        sub_traces,
        judges,
        adjudicator,
        declare_plan=False,
    )
    return report.results[0]


# ---------------------------------------------------------------------------
# 断点续跑：复用源 run 成功留痕，仅对失败/缺失用例重调 bot


def build_resume_job(
    run_id: int,
    *,
    source_run_id: int,
    run_name: str | None = None,
    settings: Settings | None = None,
) -> Callable[[InMemoryProgress], Awaitable[None]]:
    settings = settings or get_settings()

    async def job(progress: InMemoryProgress) -> None:
        src_slug, bm_id, judge_ov, adapter_ov = _load_source_run(settings, source_run_id)
        src_dir = settings.outputs_dir / src_slug
        cases, _per_case_traces, n_runs = _resume_cases_and_traces(
            src_dir, settings, bm_id
        )

        config = load_config(settings.config_path)
        if run_name:
            config.run.name = run_name
        config.run.repeat = n_runs
        _apply_judge_overrides(config, judge_ov)
        _apply_adapter_overrides(config, adapter_ov)

        adapter = build_adapter(config.adapter.type, config.adapter.model_dump())
        judges = build_judges(config.judges)
        adjudicator = build_adjudicator(config.judges)

        new_slug = make_run_slug(config.run.name)
        out_dir = settings.outputs_dir / new_slug
        # 新 run 自身也落 plan.json，使其中断后仍可续跑。
        _write_run_plan(out_dir, cases, n_runs)

        report = await evaluate(
            config,
            cases,
            adapter,
            judges,
            adjudicator,
            progress=progress,
            run_name=new_slug,
            out_dir=out_dir,
            resume_dir=src_dir,
        )

        prev = resolve_diff_target("auto", settings.outputs_dir, out_dir)
        _persist_outcome(
            run_id, report, out_dir, prev_json=prev, parent_run_id=source_run_id
        )
        _apply_retention(config, settings)

    return job
