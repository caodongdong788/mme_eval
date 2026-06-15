"""medeval 命令行入口。

用法：
  medeval run --config config.yaml
  medeval validate --config config.yaml      # 仅校验用例和配置
  medeval list-cases --config config.yaml    # 打印用例清单
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table

from . import __version__, retention, trace_store
from .adapter import build_adapter
from .config import Config, ConfigError, ThresholdsCfg
from .config import load_config as _load_config_validated
from .loader import load_cases
from .models import RunReport, TestCase
from .reporter import (
    publish_to_lark,
    publish_xlsx_to_lark,
    write_markdown,
)
from .run_slug import make_run_slug
from .service import (
    build_adjudicator,
    build_judges,
    evaluate,
    judge_traces,
    resolve_diff_target,
    write_core_artifacts,
)

console = Console()
log = logging.getLogger("medeval")


def _load_config(path: Path) -> Config:
    """加载并类型化校验 config.yaml；非法配置 fail-fast 成友好的 CLI 报错。"""
    try:
        return _load_config_validated(path)
    except ConfigError as e:
        raise click.UsageError(str(e)) from e


def _resolve_resume_dir(arg: str, outputs_dir: Path) -> Path:
    """解析 --resume 取值：绝对路径 / 已存在路径直接用，否则视为 outputs 下的 run 目录名。"""
    p = Path(arg)
    if p.is_absolute() or p.exists():
        run_dir = p
    else:
        run_dir = outputs_dir / arg
    if not run_dir.is_dir():
        raise click.UsageError(f"--resume 指定的 run 目录不存在：{run_dir}")
    return run_dir


def _print_judge_fingerprints(judges: list) -> None:
    """开跑前展示各 judge 的 fingerprint，便于人工对照报告。"""
    from rich.table import Table

    if not judges:
        return
    table = Table(title="Judge 指纹 (改动 patterns/prompt 会改变此值)")
    table.add_column("Judge")
    table.add_column("Fingerprint")
    for j in judges:
        try:
            fp = j.fingerprint()
        except Exception as e:  # pragma: no cover
            fp = f"(错误: {e})"
        table.add_row(j.name, fp)
    console.print(table)


def _print_summary(report) -> None:
    title = f"评测总览 — {report.run_name}"
    if report.n_runs > 1:
        title += f" (N={report.n_runs} majority)"
    table = Table(title=title, show_lines=False)
    table.add_column("指标", style="bold cyan")
    table.add_column("值", style="bold")
    pass_rate = (report.passed / report.total * 100) if report.total else 0.0
    hard_rate = (
        (report.total - report.hard_gate_failed) / report.total * 100
        if report.total
        else 0.0
    )
    table.add_row("总用例数", str(report.total))
    table.add_row("总通过", f"{report.passed}")
    color = "green" if pass_rate >= 85 else ("yellow" if pass_rate >= 70 else "red")
    table.add_row("总通过率", f"[{color}]{pass_rate:.1f}%[/{color}]")
    hcolor = "green" if hard_rate == 100 else "red"
    table.add_row("硬门槛通过率", f"[{hcolor}]{hard_rate:.1f}%[/{hcolor}]")
    table.add_row("硬门槛失败数", f"[red]{report.hard_gate_failed}[/red]" if report.hard_gate_failed else "0")
    if report.n_runs > 1:
        sd = report.stability_distribution or {}
        table.add_row(
            f"稳定性 (N={report.n_runs})",
            f"都过 [green]{sd.get('stable_pass', 0)}[/green] / "
            f"抖动 [yellow]{sd.get('flaky', 0)}[/yellow] / "
            f"都挂 [red]{sd.get('stable_fail', 0)}[/red]",
        )
    console.print(table)

    if report.by_level:
        lvl_table = Table(title="分层级通过率", show_lines=False)
        lvl_table.add_column("Level")
        lvl_table.add_column("总数")
        lvl_table.add_column("通过")
        lvl_table.add_column("通过率")
        lvl_table.add_column("硬门槛失败")
        for lvl in sorted(report.by_level):
            b = report.by_level[lvl]
            r = (b["passed"] / b["total"] * 100) if b["total"] else 0.0
            lvl_table.add_row(
                lvl,
                str(b["total"]),
                str(b["passed"]),
                f"{r:.1f}%",
                str(b.get("hard_failed", 0)),
            )
        console.print(lvl_table)

    if report.failure_tag_counter:
        tag_table = Table(title="Top 失败标签", show_lines=False)
        tag_table.add_column("标签", style="yellow")
        tag_table.add_column("次数")
        for tag, cnt in list(report.failure_tag_counter.items())[:10]:
            tag_table.add_row(tag, str(cnt))
        console.print(tag_table)


class RichProgress:
    """ProgressObserver 的 rich 实现：把 service 上报的 phase key 映射到 rich task。"""

    def __init__(self, progress: Progress):
        self._progress = progress
        self._tasks: dict[str, int] = {}

    def plan_phases(self, phases: list[tuple[str, str, int]]) -> None:
        # rich 逐阶段渲染独立进度条，无需预声明全局计划。
        pass

    def start_phase(self, key: str, label: str, total: int) -> None:
        self._tasks[key] = self._progress.add_task(label, total=total)

    def advance(self, key: str, n: int = 1) -> None:
        task_id = self._tasks.get(key)
        if task_id is not None:
            self._progress.update(task_id, advance=n)


@click.group()
@click.version_option(__version__)
def main():
    """medeval — 医疗 Chat Bot 自动化评测框架。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), default="config.yaml", show_default=True)
@click.option("--adapter", "adapter_override", type=str, default=None, help="覆盖 config.yaml 中的 adapter.type")
@click.option("--run-name", type=str, default=None, help="覆盖 run.name")
@click.option(
    "--score-profile",
    "score_profiles",
    type=str,
    default=None,
    help="仅运行指定 score_profile 的用例，逗号分隔（default/red_flag/adversarial/knowledge/rehab）",
)
@click.option("--limit", type=int, default=0, help="只跑前 N 条（debug 用）")
@click.option("--dry-run", is_flag=True, help="只加载用例不调用 adapter")
@click.option(
    "--repeat",
    type=int,
    default=None,
    help="每条 case 重复跑 N 次后做 majority voting (默认沿用 config.run.repeat 或 1)",
)
@click.option(
    "--diff-against",
    "diff_against_cli",
    type=str,
    default=None,
    help="对比的历史版本目录名；'auto'=自动对比上一次，'none'=不对比。默认沿用 config，否则自动",
)
@click.option(
    "--resume",
    "resume_arg",
    type=str,
    default=None,
    help="断点续跑：复用指定历史 run 目录中成功的会话留痕，只重跑缺失/失败者（仅 local 后端）",
)
def run(config_path: Path, adapter_override, run_name, score_profiles, limit, dry_run, repeat, diff_against_cli, resume_arg):
    """跑一次完整评测。"""
    config = _load_config(config_path)
    run_cfg = config.run
    reporter_cfg = config.reporter

    # CLI 覆盖（在已校验的 typed 对象上应用）
    if run_name:
        run_cfg.name = run_name
    if adapter_override:
        config.adapter.type = adapter_override
    if score_profiles:
        config.cases.score_profiles = [
            t.strip() for t in score_profiles.split(",") if t.strip()
        ]

    # --repeat 优先级：CLI > config > 默认 1。回写 typed config，作为 evaluate 的单一来源。
    if repeat is not None:
        if repeat < 1:
            raise click.BadParameter(
                f"--repeat must be a positive integer (got {repeat})", param_hint="--repeat"
            )
        run_cfg.repeat = repeat
    n_runs = run_cfg.repeat

    # reporter.formats 校验：fail-fast（在 case 加载前），避免跑完才报错
    raw_formats = reporter_cfg.formats
    if "html" in raw_formats:
        raise click.UsageError(
            "reporter.formats 中含 'html'，但 HTML 报告已下线（参见 OpenSpec "
            "change trim-report-formats）。请改为 ['markdown']；JSON 已自动写盘无需声明。"
        )

    base_dir = config_path.resolve().parent
    cases: list[TestCase] = load_cases(
        include=config.cases.include,
        exclude=config.cases.exclude,
        score_profiles=config.cases.score_profiles,
        base_dir=base_dir,
    )
    if limit:
        cases = cases[:limit]
    console.print(
        f"[bold]已加载 [cyan]{len(cases)}[/cyan] 条用例[/bold]  "
        f"(repeat={n_runs}{' · majority voting 启用' if n_runs > 1 else ''})"
    )

    if dry_run:
        return

    try:
        adapter = build_adapter(config.adapter.type, config.adapter.model_dump())
    except ValueError as e:
        # fail-fast：adapter.type 缺失或不识别 → 友好报错而非 traceback
        raise click.UsageError(str(e)) from e
    judges = build_judges(config.judges)
    adjudicator = build_adjudicator(config.judges)
    _print_judge_fingerprints(judges + ([adjudicator] if adjudicator else []))

    # 开跑前确定 run slug 与输出目录，使会话留痕可在 run 阶段增量落盘（崩溃也留得下），
    # 且 report.run_name 与落盘目录名一致。
    outputs_dir = base_dir / run_cfg.output_dir
    run_slug = make_run_slug(run_cfg.name)
    out_dir = outputs_dir / run_slug
    resume_dir = _resolve_resume_dir(resume_arg, outputs_dir) if resume_arg else None
    if resume_dir is not None:
        console.print(f"[bold]断点续跑：[/bold]复用 [cyan]{resume_dir.name}[/cyan] 的成功留痕")

    # 功能核：评测编排（run→judge→fold→report）下沉到 service.evaluate；
    # CLI 只注入 rich 进度实现，副作用（adapter 网络调用）由功能核内部完成。
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        report = asyncio.run(
            evaluate(
                config,
                cases,
                adapter,
                judges,
                adjudicator,
                progress=RichProgress(progress),
                run_name=run_slug,
                out_dir=out_dir,
                resume_dir=resume_dir,
            )
        )

    _print_summary(report)

    # raw_formats 已在前面 fail-fast 校验过 html；这里再处理 json warning。
    formats = []
    for fmt in raw_formats:
        if fmt == "json":
            console.print(
                "[yellow]ℹ[/yellow] reporter.formats 含 'json' 已被忽略：JSON 报告现在始终写盘"
            )
            continue
        formats.append(fmt)

    # 对比目标优先级：CLI --diff-against > config.reporter.diff_against > 默认自动对比上一次。
    # 取值语义：'none'/'off' 关闭；'auto' 或留空 自动对比上一次；其它视为具体版本目录名。
    diff_target = diff_against_cli if diff_against_cli is not None else (reporter_cfg.diff_against or "")
    prev_json = resolve_diff_target(diff_target, outputs_dir, out_dir)
    if prev_json is None:
        normalized = (diff_target or "").strip().lower()
        if normalized and normalized not in ("none", "off", "auto"):
            console.print(
                f"[yellow]ℹ[/yellow] 指定的对比版本不存在："
                f"{outputs_dir / diff_target.strip() / 'report.json'}，跳过 diff"
            )
        elif normalized not in ("none", "off"):
            console.print("[dim]（无历史版本可对比，跳过 diff）[/dim]")

    # 持久化层：写 report.json + diff + transcripts.xlsx（无网络、无 console）。
    artifacts = write_core_artifacts(report, out_dir, prev_json=prev_json)
    diff_summary = artifacts.diff_summary
    if prev_json is not None:
        console.print(f"[green]✓[/green] 已与上版本对比：[cyan]{prev_json.parent.name}[/cyan]")

    # transcripts.xlsx 仅作飞书导入的中间产物：生成→上传→删除，默认不在 outputs 落地。
    # 仅当飞书关闭或发布失败时，保留本地文件作兜底（否则对话流水将无任何产物）。
    transcripts_path = artifacts.transcripts_path

    # 飞书发布：默认开（参见 trim-report-formats）；显式 enabled: false 时关
    lark_cfg = reporter_cfg.lark
    lark_enabled = lark_cfg.enabled

    transcripts_url = ""
    if lark_enabled:
        sheet_url = publish_xlsx_to_lark(
            transcripts_path,
            parent_folder_token=lark_cfg.parent_folder_token,
            title=f"{report.run_name} · 对话流水",
        )
        if sheet_url:
            (out_dir / "lark_transcripts_url.txt").write_text(sheet_url)
            console.print(f"[green]✓ 飞书对话流水已发布：[/green]{sheet_url}")
            transcripts_url = sheet_url
            # 发布成功 → 删除本地中间文件，outputs 不保留 transcripts.xlsx
            transcripts_path.unlink(missing_ok=True)
        else:
            console.print(
                "[yellow]⚠ 飞书对话流水发布失败，保留本地 xlsx 作兜底[/yellow]"
            )
            transcripts_url = str(transcripts_path)
    else:
        # 飞书关闭 → 保留本地 xlsx，否则对话流水无任何产物
        transcripts_url = str(transcripts_path)

    if "markdown" in formats:
        write_markdown(
            report,
            out_dir / "report.md",
            diff_summary=diff_summary,
            transcripts_url=transcripts_url,
        )
    console.print(f"[green]✓[/green] 报告输出：{out_dir}")

    if lark_enabled:
        md_path = out_dir / "report.md"
        if md_path.exists():
            url = publish_to_lark(
                md_path.read_text(encoding="utf-8"),
                parent_folder_token=lark_cfg.parent_folder_token,
            )
            if url:
                (out_dir / "lark_url.txt").write_text(url)
                console.print(f"[green]✓ 飞书文档已发布：[/green]{url}")
            else:
                console.print("[red]✗ 飞书文档发布失败（详见日志）[/red]")
        else:
            console.print(
                "[yellow]⚠[/yellow] 飞书发布跳过：reporter.formats 不含 'markdown'，无 report.md 可推送"
            )

    # 存储治理：收尾按 retention 滚动清理历史 run 的胖产物（保 report.json）。
    ret = run_cfg.retention
    if ret.enabled:
        try:
            result = retention.prune_outputs(
                outputs_dir,
                keep_last=ret.keep_last,
                ttl_days=ret.ttl_days,
                keep_tagged=ret.keep_tagged,
            )
            if result.pruned_runs:
                console.print(
                    f"[dim]🧹 retention：已清理 {len(result.pruned_runs)} 个历史 run 的胖产物"
                    f"（保留 report.json）；保留 {len(result.kept_runs)} 个[/dim]"
                )
        except Exception as e:  # noqa: BLE001 —— 清理失败不应使评测判失败
            console.print(f"[yellow]⚠ retention 清理跳过：{e}[/yellow]")

    # 阈值断言
    if _check_thresholds(report, config.thresholds):
        sys.exit(0)
    console.print("[bold red]✗ 评测未达上线阈值[/bold red]")
    sys.exit(1)


@main.command(name="validate")
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), default="config.yaml", show_default=True)
def validate(config_path):
    """校验 config.yaml（类型化 schema）与所有用例 YAML 是否合法。"""
    config = _load_config(config_path)
    base_dir = config_path.resolve().parent
    cases = load_cases(
        include=config.cases.include,
        exclude=config.cases.exclude,
        score_profiles=config.cases.score_profiles,
        base_dir=base_dir,
    )
    console.print(f"[green]✓[/green] 配置校验通过；{len(cases)} 条用例校验通过")


@main.command(name="verify-heuristics")
def verify_heuristics():
    """启发式治理本地自检 (HardGate 关键词表).

    串联三项检查：
      1. scripts/lint_hard_gate_comments.py —— 关键词表上方 5 行注释完整性
      2. pytest tests/test_hard_gate_golden.py —— 黄金集回归
      3. scripts/check_heuristics_changelog.py —— fingerprint 与 CHANGELOG 同步

    全部通过返回 0；任一失败以非零退出码退出，并打印失败摘要。
    """
    import subprocess

    checks = [
        ("comments", [sys.executable, "scripts/lint_hard_gate_comments.py"]),
        ("golden", [sys.executable, "-m", "pytest", "tests/test_hard_gate_golden.py", "-q"]),
        ("changelog", [sys.executable, "scripts/check_heuristics_changelog.py"]),
    ]
    table = Table(title="HardGate Heuristics 自检")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    failures: list[str] = []
    for name, cmd in checks:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            table.add_row(name, "[green]✓[/green]", (result.stdout.strip().splitlines() or [""])[-1])
        else:
            failures.append(name)
            last_line = (result.stderr.strip() or result.stdout.strip()).splitlines()[-1:] or [""]
            table.add_row(name, "[red]✗[/red]", last_line[0])
    console.print(table)
    if failures:
        console.print(f"[red]✗[/red] {len(failures)} 项失败：{', '.join(failures)}")
        sys.exit(1)
    console.print("[green]✓[/green] 所有检查通过")


@main.command(name="list-cases")
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), default="config.yaml", show_default=True)
def list_cases(config_path):
    """打印用例清单。"""
    config = _load_config(config_path)
    base_dir = config_path.resolve().parent
    cases = load_cases(
        include=config.cases.include,
        exclude=config.cases.exclude,
        score_profiles=config.cases.score_profiles,
        base_dir=base_dir,
    )
    table = Table(title=f"用例清单（{len(cases)}）", show_lines=False)
    table.add_column("Sample ID")
    table.add_column("Level")
    table.add_column("Scenario")
    table.add_column("Sub")
    table.add_column("Profile")
    for c in cases:
        table.add_row(
            c.sample_id,
            c.level.value,
            c.scenario,
            c.sub_scenario,
            c.score_profile.value,
        )
    console.print(table)


@main.command(name="rejudge")
@click.argument("run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), default="config.yaml", show_default=True)
@click.option("--run-name", type=str, default=None, help="重判产物的 run.name（默认在原 name 后加 _rejudge）")
@click.option(
    "--diff-against",
    "diff_against_cli",
    type=str,
    default=None,
    help="对比目标；默认与被重判的原 run 对比（凸显判分逻辑变化）",
)
def rejudge(run_dir: Path, config_path: Path, run_name, diff_against_cli):
    """离线重判：对已落盘的冻结用例 + 冻结会话留痕重跑判分（零 adapter 调用）。

    用例取自 RUN_DIR/report.json（冻结），留痕取自 RUN_DIR/traces.jsonl.gz（冻结）。
    结果写入新的 run 目录，默认与原 run 做 diff，使「判分逻辑变化」真正单变量。
    """
    config = _load_config(config_path)
    base_dir = config_path.resolve().parent

    report_json = run_dir / "report.json"
    if not report_json.is_file():
        raise click.UsageError(f"{run_dir} 下缺 report.json，无法重判")
    prev = RunReport.model_validate_json(report_json.read_text(encoding="utf-8"))
    cases = [r.case for r in prev.results]
    if not cases:
        raise click.UsageError("原 run 无用例结果，无法重判")
    n_runs = prev.n_runs or 1

    bundle = trace_store.read_traces(run_dir)
    if bundle is not None:
        per_case_traces = bundle.per_case_traces(cases, n_runs)
        missing = [c.sample_id for c, runs in zip(cases, per_case_traces) if not runs]
        if missing:
            shown = ", ".join(missing[:5]) + ("..." if len(missing) > 5 else "")
            raise click.UsageError(f"以下用例缺会话留痕，无法重判：{shown}")
    else:
        if n_runs > 1:
            raise click.UsageError(
                f"{run_dir} 缺 traces.jsonl.gz 且原 run n_runs={n_runs}>1，"
                "代表性 trace 不足以重做 majority voting。"
            )
        per_case_traces = [[r.trace] for r in prev.results]
        console.print(
            "[yellow]ℹ 未找到 traces.jsonl.gz，回退用 report.json 代表性 trace 重判（n_runs=1）[/yellow]"
        )

    # fold / 进度口径以原 run 的 n_runs 为准
    config.run.repeat = n_runs

    judges = build_judges(config.judges)
    adjudicator = build_adjudicator(config.judges)
    _print_judge_fingerprints(judges + ([adjudicator] if adjudicator else []))

    new_slug = make_run_slug(run_name or f"{config.run.name}_rejudge")
    outputs_dir = base_dir / config.run.output_dir
    out_dir = outputs_dir / new_slug

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        report = asyncio.run(
            judge_traces(
                config,
                cases,
                per_case_traces,
                judges,
                adjudicator,
                progress=RichProgress(progress),
                run_name=new_slug,
                declare_plan=True,
            )
        )

    _print_summary(report)

    if diff_against_cli is not None:
        prev_json = resolve_diff_target(diff_against_cli, outputs_dir, out_dir)
    else:
        prev_json = report_json  # 默认与被重判的原 run 对比

    artifacts = write_core_artifacts(report, out_dir, prev_json=prev_json)
    write_markdown(
        report,
        out_dir / "report.md",
        diff_summary=artifacts.diff_summary,
        transcripts_url=str(artifacts.transcripts_path),
    )
    console.print(f"[green]✓[/green] 重判报告输出：{out_dir}")
    if prev_json is not None:
        console.print(
            f"[green]✓[/green] 已与 [cyan]{prev_json.parent.name}[/cyan] 对比（判分逻辑变化）"
        )


@main.command(name="prune")
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), default="config.yaml", show_default=True)
@click.option("--keep-last", type=int, default=None, help="保留最近 N 个 run 的胖产物（默认取 config.run.retention.keep_last）")
@click.option("--ttl-days", type=int, default=None, help="清理早于 N 天的 run 胖产物（默认取 config）")
@click.option("--dry-run", is_flag=True, help="只预览将清理的产物，不实际删除")
def prune(config_path: Path, keep_last, ttl_days, dry_run):
    """按 retention 策略清理历史 run 的胖产物（traces/xlsx），永久保留 report.json。"""
    config = _load_config(config_path)
    base_dir = config_path.resolve().parent
    outputs_dir = base_dir / config.run.output_dir
    ret = config.run.retention
    kl = keep_last if keep_last is not None else ret.keep_last
    ttl = ttl_days if ttl_days is not None else ret.ttl_days
    result = retention.prune_outputs(
        outputs_dir,
        keep_last=kl,
        ttl_days=ttl,
        keep_tagged=ret.keep_tagged,
        dry_run=dry_run,
    )
    verb = "将清理" if dry_run else "已清理"
    console.print(
        f"[bold]{verb}[/bold] {len(result.pruned_runs)} 个 run 的胖产物，"
        f"保留 {len(result.kept_runs)} 个（report.json 永久保留）"
    )
    for f in result.removed_files:
        console.print(f"[dim]  - {f}[/dim]")
    if dry_run and result.removed_files:
        console.print("[yellow]（--dry-run：未实际删除任何文件）[/yellow]")


def _check_thresholds(report, thr: ThresholdsCfg) -> bool:
    # 未配置任何阈值（整段缺省）→ 不做断言（与历史 `not thr` 行为一致）。
    configured = any(
        v is not None
        for v in (
            thr.hard_gate_pass_rate,
            thr.overall_pass_rate,
            thr.l3_red_flag_pass_rate,
            thr.l2_business_pass_rate,
            thr.l4_adversarial_pass_rate,
        )
    )
    if not configured or report.total == 0:
        return True
    pass_rate = report.passed / report.total
    hard_rate = (report.total - report.hard_gate_failed) / report.total
    ok = True
    msg = []

    # 缺省值沿用历史 `.get(k, default)` 口径：hard_gate=1.0 / overall=0.0 / l3=1.0
    hgpr = thr.hard_gate_pass_rate if thr.hard_gate_pass_rate is not None else 1.0
    opr = thr.overall_pass_rate if thr.overall_pass_rate is not None else 0.0
    l3pr = thr.l3_red_flag_pass_rate if thr.l3_red_flag_pass_rate is not None else 1.0

    if hard_rate < hgpr:
        ok = False
        msg.append(f"硬门槛通过率 {hard_rate*100:.1f}% < {hgpr*100:.1f}%")
    if pass_rate < opr:
        ok = False
        msg.append(f"总通过率 {pass_rate*100:.1f}% < {opr*100:.1f}%")
    # L3 红旗集
    by_level = report.by_level.get("L3") or {}
    if by_level.get("total"):
        l3_rate = by_level["passed"] / by_level["total"]
        if l3_rate < l3pr:
            ok = False
            msg.append(f"L3 红旗通过率 {l3_rate*100:.1f}% < {l3pr*100:.1f}%")
    for line in msg:
        console.print(f"[red]  ✗ {line}[/red]")
    return ok


if __name__ == "__main__":
    main()
