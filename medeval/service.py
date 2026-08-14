"""评测服务层 —— 功能核 / 持久化层，与 CLI 命令式外壳解耦。

参见 OpenSpec change ``2026-06-02-extract-evaluation-service``。

分层：
  * **功能核** ``evaluate``：纯编排，唯一副作用是 adapter 网络调用；输入校验后的
    ``Config`` + 用例 + 注入的 adapter/judges，输出 ``RunReport``。
    不依赖 click / console / sys.exit / 文件写盘；进度经注入式 ``ProgressObserver`` 上报。
  * **持久化层** ``resolve_diff_target`` / ``write_core_artifacts``：文件副作用集中，
    可在临时目录、无网络、无 console 地被测。
  * **构造器** ``build_judges``：从 typed config 装配八维和指南判官。

CLI（``medeval/cli.py``）作为命令式外壳，注入 rich 进度实现、负责飞书发布、终端总览与退出码。
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from . import trace_store
from .config import Config, JudgesCfg
from .judges import (
    EightDimensionJudge,
    GuidelineJudge,
    judge_all,
)
from .models import CaseResult, ConversationTrace, RunReport, TestCase, Turn
from .observability import langfuse_tracing as lf
from .observability.tracing import configure_tracing, span
from .reporter import build_report, diff_runs, write_json, write_transcripts_xlsx
from .reporter.scoring import apply_grading
from .run_slug import make_run_slug
from .runner import fold_n_runs, run_cases
from .runner.user_simulator import UserSimulator


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


async def _notify_case_completed(
    progress: ProgressObserver, result: CaseResult
) -> None:
    """可选扩展事件：不扩大 ProgressObserver 的强制协议，保持现有调用方兼容。"""
    callback = getattr(progress, "case_completed", None)
    if callback is None:
        return
    pending = callback(result)
    if inspect.isawaitable(pending):
        await pending


# ---------------------------------------------------------------------------
# 构造器：从 typed config 装配判官（迁自 cli）。


def build_judges(jcfg: JudgesCfg, *, trigger_aware: bool = True) -> list:
    judges: list = []
    for cfg, judge_type in (
        (jcfg.eight_dimension, EightDimensionJudge),
        (jcfg.guideline, GuidelineJudge),
    ):
        if cfg.enabled:
            options = {
                "enabled": True,
                "provider": cfg.provider,
                "model": cfg.model,
                "api_key_env": cfg.api_key_env,
                "api_key": cfg.api_key,
                "base_url": cfg.base_url,
                "temperature": cfg.temperature,
                "api_version": cfg.api_version,
                "default_headers": cfg.default_headers,
                "enable_thinking": cfg.enable_thinking,
            }
            if judge_type is GuidelineJudge:
                options["trigger_aware"] = trigger_aware
            judges.append(judge_type(**options))
    return judges


def build_user_simulator(config: Config) -> UserSimulator:
    """构造动态多轮用户模拟器；规则/脚本模式在 disabled 时仍可工作。"""
    cfg = config.user_simulator
    return UserSimulator(
        enabled=cfg.enabled,
        provider=cfg.provider,
        model=cfg.model,
        api_key_env=cfg.api_key_env,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        temperature=cfg.temperature,
        api_version=cfg.api_version,
        default_headers=cfg.default_headers,
        enable_thinking=cfg.enable_thinking,
        cache_dir=Path(config.run.output_dir) / cfg.cache_subdir,
    )


def execution_cases_for_mode(config: Config, cases: list[TestCase]) -> list[TestCase]:
    """按本次 Run 的对话模式准备执行用例，不改写原始 Case 或判分依据。

    ``single_turn`` 保留 main 分支的固定 turns 执行器语义。动态 Case 会被临时展平为
    opening + follow_ups，忽略语义路由和用户模拟器；Judge 仍拿原始 Case 与真实 trace
    判分，因此 YAML、画像和指南均完整保留在报告中。
    """
    if config.run.evaluation_mode != "single_turn":
        return cases

    converted: list[TestCase] = []
    for case in cases:
        plan = case.conversation
        if plan is None:
            converted.append(case)
            continue
        static_turns: list[Turn] = []
        for source_turn in (plan.opening, *plan.follow_ups):
            turn = Turn(role="user", content=source_turn.content, images=list(source_turn.images))
            turn.attach_image_data_urls(source_turn.image_data_urls)
            static_turns.append(turn)
        converted.append(case.model_copy(update={"turns": static_turns, "conversation": None}))
    return converted


# ---------------------------------------------------------------------------
# 功能核：跑评测 → 判分 → 折叠 → RunReport（唯一副作用 = adapter 网络调用）。


def run_phase_plan(n_cases: int, n_runs: int) -> list[tuple[str, str, int]]:
    """run 阶段的进度 plan（调 chatbot）。"""
    return [("run", "调用 chatbot", n_cases * n_runs)]


def judge_phase_plan(
    n_cases: int, n_runs: int, judges: list
) -> list[tuple[str, str, int]]:
    """judge 阶段的进度 plan。"""
    return [
        (
            f"judge_{judge.name}",
            "Judge 判分 (八维)" if judge.name == "dimension" else "Judge 判分 (指南)",
            n_cases * n_runs,
        )
        for judge in judges
    ]


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
    account_owner: str = "",
    on_case_complete=None,
) -> list[list[ConversationTrace]]:
    """run 阶段：唯一 adapter 副作用，产出 ``list[list[ConversationTrace]]``。

    * ``out_dir`` + ``config.run.persist_traces`` → 增量落盘 ``traces.partial.jsonl``，
      run 阶段结束即 ``finalize_traces`` 压缩为 ``traces.jsonl.gz``（崩溃也留得下）。
    * ``resume_dir`` → 加载其成功留痕做断点续跑（adapter 指纹不一致则拒绝）。
    """
    progress = progress or NullProgress()
    execution_cases = execution_cases_for_mode(config, cases)
    n_runs = config.run.repeat
    concurrency = config.run.concurrency
    n_cases = len(execution_cases)
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
    index_by_id = {c.sample_id: i for i, c in enumerate(execution_cases)}

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
                execution_cases,
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
                account_owner=account_owner,
                user_simulator=build_user_simulator(config),
                on_case_complete=on_case_complete,
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
    *,
    progress: ProgressObserver | None = None,
    started_at: datetime | None = None,
    run_name: str | None = None,
    declare_plan: bool = True,
) -> RunReport:
    """judge 阶段：对每次冻结会话运行八维和指南判分，再折叠多次结果。

    **纯判分、零 adapter 调用**——是离线重判（``medeval rejudge``）的根本前提。
    ``declare_plan=True``（rejudge 独立调用）时自行声明 judge-only plan；
    被 ``evaluate`` 编排时传 False（plan 已在编排层一次性声明）。
    """
    progress = progress or NullProgress()
    started_at = started_at or datetime.utcnow()
    n_runs = config.run.repeat
    judge_concurrency = config.run.judge_concurrency
    from .judges.llm_backend import configure_llm_rate_limit

    configure_llm_rate_limit(judge_concurrency, config.run.llm_min_interval_s)
    if declare_plan:
        progress.plan_phases(judge_phase_plan(len(cases), n_runs, judges))

    for judge in judges:
        progress.start_phase(
            f"judge_{judge.name}",
            "Judge 判分 (八维)" if judge.name == "dimension" else "Judge 判分 (指南)",
            len(cases) * n_runs,
        )

    folded_results: list[CaseResult | None] = [None for _ in cases]
    judge_sem = asyncio.Semaphore(judge_concurrency)

    async def _judge_case(idx: int, case, runs):
        run_results: list[CaseResult] = []
        for trace in runs:
            async with judge_sem:
                r = await judge_all(case, trace, judges)
                apply_grading([r])
            for judge in judges:
                progress.advance(f"judge_{judge.name}")
            run_results.append(r)
        folded = fold_n_runs([run_results])[0]
        folded_results[idx] = folded
        await _notify_case_completed(progress, folded)

    with span("phase.judge", n_cases=len(cases), n_runs=n_runs):
        await asyncio.gather(
            *(
                _judge_case(i, c, runs)
                for i, (c, runs) in enumerate(zip(cases, per_case_traces))
            )
        )

    # 每条用例已在完成时独立折叠；按输入顺序组装最终报告，确保与历史输出稳定一致。
    if any(result is None for result in folded_results):
        raise RuntimeError("judge_traces 未生成完整的用例结果")
    folded = [result for result in folded_results if result is not None]

    return build_report(
        run_name=run_name or make_run_slug(config.run.name),
        results=folded,
        adapter_type=config.adapter.type,
        config_snapshot=config.public_snapshot(),
        description=config.run.description,
        started_at=started_at,
        n_runs=n_runs,
    )


async def evaluate(
    config: Config,
    cases: list[TestCase],
    adapter,
    judges: list,
    *,
    progress: ProgressObserver | None = None,
    run_name: str | None = None,
    account_owner: str = "",
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
    # 平台可能另外展示按 Case 聚合的进度；这是可选扩展，保持 SDK/旧观察者兼容。
    set_case_total = getattr(progress, "set_case_total", None)
    if callable(set_case_total):
        set_case_total(len(cases))

    try:
        # Judge 与 bot 调用并行流水：某条 Case 的全部对话完成后，立即判分、折叠并
        # 通知平台落库，不等待整个 benchmark 的所有对话执行完毕。
        for judge in judges:
            progress.start_phase(
                f"judge_{judge.name}",
                "Judge 判分 (八维)" if judge.name == "dimension" else "Judge 判分 (指南)",
                len(cases) * n_runs,
            )
        folded_results: list[CaseResult | None] = [None for _ in cases]
        judge_sem = asyncio.Semaphore(config.run.judge_concurrency)

        async def judge_completed_case(
            index: int, _execution_case: TestCase, traces: list[ConversationTrace]
        ) -> None:
            # single_turn 模式会临时展平动态对话；判分仍必须使用原始 Case 真值。
            case = cases[index]
            run_results: list[CaseResult] = []
            for trace in traces:
                async with judge_sem:
                    result = await judge_all(case, trace, judges)
                    apply_grading([result])
                for judge in judges:
                    progress.advance(f"judge_{judge.name}")
                run_results.append(result)
            folded = fold_n_runs([run_results])[0]
            folded_results[index] = folded
            await _notify_case_completed(progress, folded)

        # 每条用例独立成一条 Langfuse trace（按 session=run_name 分组，整段 run 可在
        # Sessions 视图整体回放）；judge 调用不纳入追踪。
        await run_traces(
            config,
            cases,
            adapter,
            progress=progress,
            run_name=run_name or "",
            account_owner=account_owner,
            out_dir=Path(out_dir) if out_dir is not None else None,
            resume_dir=Path(resume_dir) if resume_dir is not None else None,
            on_case_complete=judge_completed_case,
        )
        if any(result is None for result in folded_results):
            raise RuntimeError("evaluate 未生成完整的用例结果")
        report = build_report(
            run_name=run_name or make_run_slug(config.run.name),
            results=[result for result in folded_results if result is not None],
            adapter_type=config.adapter.type,
            config_snapshot=config.public_snapshot(),
            description=config.run.description,
            started_at=started_at,
            n_runs=n_runs,
        )

        return report
    finally:
        # 失败、取消和服务关闭时也必须释放 cx-agent 账号租约，避免依赖租约 TTL 回收。
        await adapter.close()
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
