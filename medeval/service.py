"""评测服务层 —— 功能核 / 持久化层，与 CLI 命令式外壳解耦。

参见 OpenSpec change ``2026-06-02-extract-evaluation-service``。

分层：
  * **功能核** ``evaluate``：纯编排，唯一副作用是 adapter 网络调用；输入校验后的
    ``Config`` + 用例 + 注入的 adapter/judges/adjudicator，输出 ``RunReport``。
    不依赖 click / console / sys.exit / 文件写盘；进度经注入式 ``ProgressObserver`` 上报。
  * **持久化层** ``resolve_diff_target`` / ``write_core_artifacts``：文件副作用集中，
    可在临时目录、无网络、无 console 地被测。
  * **构造器** ``build_judges`` / ``build_adjudicator``：从 typed config 装配判官。

CLI（``medeval/cli.py``）作为命令式外壳，注入 rich 进度实现、负责飞书发布、终端总览与退出码。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from . import trace_store
from .config import Config, JudgesCfg
from .judges import (
    HardGateJudge,
    LLMJudge,
    RuleJudge,
    ScoringPointJudge,
    SemanticRuleAdjudicator,
    compute_guideline_match_rate,
    judge_all,
)
from .models import CaseResult, ConversationTrace, RunReport, TestCase
from .observability import langfuse_tracing as lf
from .observability.tracing import configure_tracing, span
from .reporter import build_report, diff_runs, write_json, write_transcripts_xlsx
from .run_slug import make_run_slug
from .runner import fold_n_runs, run_cases


# ---------------------------------------------------------------------------
# 进度解耦：功能核只发 phase 事件，不绑定具体 UI（rich）。


class ProgressObserver(Protocol):
    """评测进度观察者。phase key：run / judge_det / judge_llm / judge_sp。"""

    def plan_phases(self, phases: list[tuple[str, str, int]]) -> None: ...

    def start_phase(self, key: str, label: str, total: int) -> None: ...

    def advance(self, key: str, n: int = 1) -> None: ...


class NullProgress:
    """默认 no-op 进度观察者（SDK / 测试不关心进度时使用）。"""

    def plan_phases(self, phases: list[tuple[str, str, int]]) -> None:  # noqa: D401
        pass

    def start_phase(self, key: str, label: str, total: int) -> None:  # noqa: D401
        pass

    def advance(self, key: str, n: int = 1) -> None:
        pass


# ---------------------------------------------------------------------------
# 构造器：从 typed config 装配判官（迁自 cli）。


def build_judges(jcfg: JudgesCfg) -> list:
    judges: list = []
    if jcfg.hard_gates.enabled:
        judges.append(HardGateJudge())
    if jcfg.rule.enabled:
        judges.append(RuleJudge(normalize=jcfg.rule.normalize))
    llm = jcfg.llm
    if llm.enabled:
        judges.append(
            LLMJudge(
                enabled=True,
                provider=llm.provider,
                model=llm.model,
                api_key_env=llm.api_key_env,
                api_key=llm.api_key,
                base_url=llm.base_url,
                temperature=llm.temperature,
                dual_judge=llm.dual_judge,
                second_model=llm.second_model,
                api_version=llm.api_version,
                default_headers=llm.default_headers,
                self_consistency=llm.self_consistency,
                aggregate=llm.aggregate,
            )
        )
    sp = jcfg.scoring_point
    if sp.enabled:
        judges.append(
            ScoringPointJudge(
                enabled=True,
                provider=sp.provider,
                model=sp.model,
                api_key_env=sp.api_key_env,
                api_key=sp.api_key,
                base_url=sp.base_url,
                temperature=sp.temperature,
                api_version=sp.api_version,
                default_headers=sp.default_headers,
                self_consistency=sp.self_consistency,
            )
        )
    return judges


def build_adjudicator(jcfg: JudgesCfg) -> SemanticRuleAdjudicator | None:
    """构造语义裁决器（独立角色，不进 judge_all 列表）。未启用时返回 None。"""
    sa = jcfg.rule.semantic_adjudicator
    if not sa.enabled:
        return None
    return SemanticRuleAdjudicator(
        enabled=True,
        provider=sa.provider,
        model=sa.model,
        api_key_env=sa.api_key_env,
        api_key=sa.api_key,
        base_url=sa.base_url,
        temperature=sa.temperature,
        api_version=sa.api_version,
        default_headers=sa.default_headers,
        negation_prefilter_enabled=sa.negation_prefilter.enabled,
        negation_cues=sa.negation_prefilter.cues or None,
        cache_enabled=sa.cache.enabled,
    )


# ---------------------------------------------------------------------------
# 功能核：跑评测 → 判分 → 折叠 → RunReport（唯一副作用 = adapter 网络调用）。


def _split_judges(judges: list):
    """从 judge 列表拆出确定性 judge 与 LLM 类 judge（llm / scoring_point）。

    LLM 类 judge 在 majority 之后只对代表性 trace 各跑一次（控成本），故需单列。
    """
    llm_like = {"llm", "scoring_point"}
    deterministic = [j for j in judges if j.name not in llm_like]
    llm_judge = next((j for j in judges if j.name == "llm"), None)
    scoring_judge = next((j for j in judges if j.name == "scoring_point"), None)
    return deterministic, llm_judge, scoring_judge


def run_phase_plan(n_cases: int, n_runs: int) -> list[tuple[str, str, int]]:
    """run 阶段的进度 plan（调 chatbot）。"""
    return [("run", "调用 chatbot", n_cases * n_runs)]


def judge_phase_plan(
    n_cases: int, n_runs: int, judges: list
) -> list[tuple[str, str, int]]:
    """judge 阶段的进度 plan（确定性 + 可选 llm / 得分点）。"""
    _, llm_judge, scoring_judge = _split_judges(judges)
    plan: list[tuple[str, str, int]] = [
        ("judge_det", "Judge 判分 (确定性)", n_cases * n_runs),
    ]
    if llm_judge is not None:
        plan.append(("judge_llm", "Judge 判分 (LLM)", n_cases))
    if scoring_judge is not None:
        plan.append(("judge_sp", "Judge 判分 (得分点)", n_cases))
    return plan


async def run_traces(
    config: Config,
    cases: list[TestCase],
    adapter,
    *,
    progress: ProgressObserver | None = None,
    out_dir: Path | None = None,
    resume_dir: Path | None = None,
    adapter_config: dict | None = None,
    run_name: str = "",
) -> list[list[ConversationTrace]]:
    """run 阶段：唯一 adapter 副作用，产出 ``list[list[ConversationTrace]]``。

    * ``out_dir`` + ``config.run.persist_traces`` → 增量落盘 ``traces.partial.jsonl``，
      run 阶段结束即 ``finalize_traces`` 压缩为 ``traces.jsonl.gz``（崩溃也留得下）。
    * ``resume_dir`` → 加载其成功留痕做断点续跑（adapter 指纹不一致则拒绝）。
    """
    progress = progress or NullProgress()
    n_runs = config.run.repeat
    concurrency = config.run.concurrency
    n_cases = len(cases)
    adapter_cfg = adapter_config if adapter_config is not None else config.adapter.model_dump()
    fp = trace_store.adapter_fingerprint(config.adapter.type, adapter_cfg)

    # 断点续跑：加载上次成功留痕（error 为空者），adapter 指纹不一致则拒绝复用。
    resume_index = None
    if resume_dir is not None:
        bundle = trace_store.read_traces(Path(resume_dir))
        if bundle is None:
            raise RuntimeError(
                f"断点续跑失败：{resume_dir} 下无可复用留痕（traces.jsonl.gz / partial）"
            )
        prev_fp = bundle.meta.get("adapter_fingerprint")
        if prev_fp and prev_fp != fp:
            raise RuntimeError(
                f"断点续跑失败：adapter 指纹不一致（当前 {fp} vs 留痕 {prev_fp}），"
                "拒绝把不同 bot 的旧留痕混入本次结果。"
            )
        resume_index = {k: t for k, t in bundle.by_key.items() if t.error is None}

    # 落盘 writer：仅在给定 out_dir 且开启 persist 时启用（平台/SDK/测试不传 out_dir → 不落盘）。
    writer = None
    persist = out_dir is not None and config.run.persist_traces
    if persist:
        meta = {
            "schema": trace_store.SCHEMA_VERSION,
            "adapter_fingerprint": fp,
            "store_raw": config.run.store_raw,
            "n_runs": n_runs,
            "n_cases": n_cases,
        }
        writer = trace_store.PartialTraceWriter(
            Path(out_dir), store_raw=config.run.store_raw, meta=meta
        )
    index_by_id = {c.sample_id: i for i, c in enumerate(cases)}

    progress.start_phase("run", "调用 chatbot", n_cases * n_runs)

    def on_run(case=None, trace=None, run_idx=0):
        progress.advance("run")
        if writer is not None and case is not None and trace is not None:
            writer.record(case.sample_id, index_by_id.get(case.sample_id, -1), run_idx, trace)

    try:
        with span(
            "phase.run",
            n_cases=n_cases,
            n_runs=n_runs,
            concurrency=concurrency,
            executor=config.run.executor,
        ):
            per_case_traces = await run_cases(
                cases,
                adapter,
                concurrency=concurrency,
                timeout_s=config.run.timeout_s,
                retry=config.run.retry,
                repeat=n_runs,
                on_progress=on_run,
                retry_backoff_base_s=config.run.retry_backoff_base_s,
                retry_backoff_max_s=config.run.retry_backoff_max_s,
                executor=config.run.executor,
                adapter_type=config.adapter.type,
                adapter_config=adapter_cfg,
                ray_address=config.run.ray_address,
                ray_num_workers=config.run.ray_num_workers,
                resume_index=resume_index,
                run_name=run_name,
            )
    finally:
        if writer is not None:
            writer.close()
    if persist:
        trace_store.finalize_traces(Path(out_dir))
    return per_case_traces


async def judge_traces(
    config: Config,
    cases: list[TestCase],
    per_case_traces: list[list[ConversationTrace]],
    judges: list,
    adjudicator,
    *,
    progress: ProgressObserver | None = None,
    started_at: datetime | None = None,
    run_name: str | None = None,
    declare_plan: bool = True,
) -> RunReport:
    """judge 阶段：对（冻结的）会话留痕判分→fold→llm→sp→软分→build_report。

    **纯判分、零 adapter 调用**——是离线重判（``medeval rejudge``）的根本前提。
    ``declare_plan=True``（rejudge 独立调用）时自行声明 judge-only plan；
    被 ``evaluate`` 编排时传 False（plan 已在编排层一次性声明）。
    """
    progress = progress or NullProgress()
    started_at = started_at or datetime.utcnow()
    n_runs = config.run.repeat
    concurrency = config.run.concurrency
    judge_concurrency = config.run.judge_concurrency
    from .judges.llm_backend import configure_llm_rate_limit

    configure_llm_rate_limit(judge_concurrency, config.run.llm_min_interval_s)
    deterministic_judges, llm_judge, scoring_judge = _split_judges(judges)

    if declare_plan:
        progress.plan_phases(judge_phase_plan(len(cases), n_runs, judges))

    progress.start_phase("judge_det", "Judge 判分 (确定性)", len(cases) * n_runs)
    # 每次 (case, run) 跑确定性 judge —— 跨 case 并发（同一 case 内逐 run 顺序，
    # 保证 stability 口径一致；adjudicator 在 majority 之前逐 run 介入）。
    per_case_results: list[list[CaseResult]] = [[] for _ in cases]
    det_sem = asyncio.Semaphore(concurrency)

    async def _judge_case(idx: int, case, runs):
        async with det_sem:
            run_results: list[CaseResult] = []
            for trace in runs:
                r = await judge_all(case, trace, deterministic_judges)
                if adjudicator is not None:
                    r = await adjudicator.adjudicate(r)
                run_results.append(r)
                progress.advance("judge_det")
            per_case_results[idx] = run_results

    with span("phase.judge_det", n_cases=len(cases), n_runs=n_runs):
        await asyncio.gather(
            *(
                _judge_case(i, c, runs)
                for i, (c, runs) in enumerate(zip(cases, per_case_traces))
            )
        )

    # majority voting
    folded = fold_n_runs(per_case_results)

    # LLM Judge 仅对代表性 trace 跑一次（控成本）—— 跨 case 并发
    if llm_judge is not None:
        progress.start_phase("judge_llm", "Judge 判分 (LLM)", len(folded))
        llm_fp = ""
        try:
            llm_fp = llm_judge.fingerprint()
        except Exception:
            pass
        llm_sem = asyncio.Semaphore(judge_concurrency)

        async def _llm_one(r):
            async with llm_sem:
                with span("judge.llm", sample_id=r.case.sample_id):
                    llm_verdicts = await llm_judge.judge(r.case, r.trace)
                for v in llm_verdicts:
                    if not v.judge_fingerprint:
                        v.judge_fingerprint = llm_fp
                r.verdicts.extend(llm_verdicts)
                progress.advance("judge_llm")

        with span("phase.judge_llm", n_cases=len(folded)):
            await asyncio.gather(*(_llm_one(r) for r in folded))

    # 得分点判官同样仅对代表性 trace 跑一次（控成本），并派生指南匹配率
    if scoring_judge is not None:
        progress.start_phase("judge_sp", "Judge 判分 (得分点)", len(folded))
        sp_fp = ""
        try:
            sp_fp = scoring_judge.fingerprint()
        except Exception:
            pass
        sp_sem = asyncio.Semaphore(judge_concurrency)

        async def _sp_one(r):
            async with sp_sem:
                with span("judge.scoring_point", sample_id=r.case.sample_id):
                    sp_verdicts = await scoring_judge.judge(r.case, r.trace)
                for v in sp_verdicts:
                    if not v.judge_fingerprint:
                        v.judge_fingerprint = sp_fp
                r.verdicts.extend(sp_verdicts)
                if sp_verdicts:
                    r.guideline_match_rate = compute_guideline_match_rate(
                        r.case, sp_verdicts
                    )
                progress.advance("judge_sp")

        with span("phase.judge_sp", n_cases=len(folded)):
            await asyncio.gather(*(_sp_one(r) for r in folded))

    # 软分重新累计（确定性 judge 不贡献软分）：llm.* + scoring_point.summary
    for r in folded:
        soft = [
            v
            for v in r.verdicts
            if v.name.startswith("llm.") or v.name == "scoring_point.summary"
        ]
        r.soft_score = sum(v.score for v in soft)
        r.soft_score_max = sum(v.max_score for v in soft)

    return build_report(
        run_name=run_name or make_run_slug(config.run.name),
        results=folded,
        adapter_type=config.adapter.type,
        config_snapshot=config.model_dump(mode="json"),
        description=config.run.description,
        started_at=started_at,
        n_runs=n_runs,
    )


async def evaluate(
    config: Config,
    cases: list[TestCase],
    adapter,
    judges: list,
    adjudicator,
    *,
    progress: ProgressObserver | None = None,
    run_name: str | None = None,
    out_dir: Path | None = None,
    resume_dir: Path | None = None,
) -> RunReport:
    """完整评测编排：run_traces + judge_traces。不打印、不退出。

    * 不传 ``out_dir``/``run_name``/``resume_dir``（平台 / SDK / 测试）→ 行为与现状逐字段一致、不落盘。
    * 传 ``out_dir`` → 会话留痕落盘到该目录（``run_name`` 应等于其目录名，使
      ``report.run_name`` 与落盘目录一致）；``resume_dir`` → 断点续跑。
    """
    progress = progress or NullProgress()
    started_at = datetime.utcnow()
    n_runs = config.run.repeat

    # 可选 OTel tracing：默认关闭、no-op；启用时为各 phase / adapter / judge 调用记 span。
    # 配置失败或未装 otel 时自动退化为 no-op，绝不影响主链路。
    configure_tracing(
        enabled=config.observability.otel.enabled,
        endpoint=config.observability.otel.endpoint,
        service_name=config.observability.otel.service_name,
    )

    # 可选 Langfuse 追踪（bot-only）：默认关闭、no-op；启用时被测 bot 每个 user turn 记一个
    # generation，会话/turn 嵌在 run 级 root trace 下。凭据仅从环境变量读，未装/失败自动退化。
    lf.configure_from_env(config.observability.langfuse)

    # 开跑前一次性声明完整阶段计划（run + judge），让进度观察者按全局总量算单调百分比。
    progress.plan_phases(
        run_phase_plan(len(cases), n_runs) + judge_phase_plan(len(cases), n_runs, judges)
    )

    try:
        # 每条用例独立成一条 Langfuse trace（按 session=run_name 分组，整段 run 可在
        # Sessions 视图整体回放）；judge 调用不纳入追踪。
        per_case_traces = await run_traces(
            config,
            cases,
            adapter,
            progress=progress,
            run_name=run_name or "",
            out_dir=Path(out_dir) if out_dir is not None else None,
            resume_dir=Path(resume_dir) if resume_dir is not None else None,
        )

        report = await judge_traces(
            config,
            cases,
            per_case_traces,
            judges,
            adjudicator,
            progress=progress,
            started_at=started_at,
            run_name=run_name,
            declare_plan=False,
        )

        await adapter.close()
        return report
    finally:
        # 短命进程收尾 flush，保证缓冲的 trace 不丢；关闭/失败时为 no-op。
        lf.flush()


# ---------------------------------------------------------------------------
# 持久化层（文件副作用集中，可在 tmp 目录测、无网络、无 console）。


def _find_previous_run(outputs_dir: Path, current_dir: Path) -> Path | None:
    """返回 outputs/ 下除当前 run 外、最近一次（按 report.json 修改时间）的报告路径。

    用于"默认自动对比上一个版本"：当前 run 的目录已写入 report.json，
    按 mtime 取次新者即为时间上的上一次评测。无历史时返回 None。
    """
    if not outputs_dir.is_dir():
        return None
    current = current_dir.resolve()
    candidates: list[Path] = []
    for d in outputs_dir.iterdir():
        if not d.is_dir() or d.resolve() == current:
            continue
        report_json = d / "report.json"
        if report_json.is_file():
            candidates.append(report_json)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def resolve_diff_target(
    diff_target: str, outputs_dir: Path, out_dir: Path
) -> Path | None:
    """解析版本对比目标 → 上一版 report.json 路径（或 None）。

    取值语义：'none'/'off' 关闭；'auto' 或留空 自动对比上一次；其它视为具体版本目录名。
    指定的版本目录不存在时返回 None（由调用方决定如何提示）。
    """
    target = (diff_target or "").strip()
    if target.lower() in ("none", "off"):
        return None
    if target and target.lower() != "auto":
        prev = outputs_dir / target / "report.json"
        return prev if prev.is_file() else None
    return _find_previous_run(outputs_dir, out_dir)


@dataclass
class Artifacts:
    report_json: Path
    diff_summary: str
    transcripts_path: Path


def write_core_artifacts(
    report: RunReport, out_dir: Path, *, prev_json: Path | None
) -> Artifacts:
    """写核心产物：report.json（始终）+ diff（有 prev 时）+ transcripts.xlsx。

    不写 report.md（其需嵌入飞书 sheet URL，时序上由 CLI 在发布后再写），不发飞书、不打印。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    report_json = out_dir / "report.json"
    write_json(report, report_json)

    diff_summary = ""
    if prev_json is not None:
        diff_summary = diff_runs(report_json, prev_json)

    transcripts_path = out_dir / "transcripts.xlsx"
    write_transcripts_xlsx(report, transcripts_path)

    return Artifacts(
        report_json=report_json,
        diff_summary=diff_summary,
        transcripts_path=transcripts_path,
    )
