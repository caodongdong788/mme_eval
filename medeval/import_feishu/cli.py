"""import-feishu 命令实现。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console

from ..config import load_config
from .assemble import rows_to_cases
from .case_enrich import enrich_case_fields
from .sheet_fetch import LarkCliError, fetch_sheet_grid
from .sheet_parse import parse_scoring_points, parse_sheet_rows

log = logging.getLogger(__name__)
console = Console()


def _write_import_report(
    path: Path,
    entries: list[dict[str, Any]],
) -> None:
    path.write_text(
        json.dumps({"cases": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_import(
    *,
    sheet_url: str,
    out: Path,
    config_path: Path,
    worksheet: str | None,
    id_prefix: str,
    enrich: bool,
    skip_validate: bool,
    dry_run: bool,
) -> int:
    try:
        grid = fetch_sheet_grid(sheet_url, worksheet=worksheet)
    except LarkCliError as exc:
        console.print(f"[red]拉取飞书表格失败:[/red] {exc}")
        return 1

    try:
        rows = parse_sheet_rows(grid)
    except ValueError as exc:
        console.print(f"[red]解析表格失败:[/red] {exc}")
        return 1

    if not rows:
        console.print("[yellow]未解析到有效数据行（需至少一列「第N轮」有内容）[/yellow]")
        return 1

    console.print(f"已解析 [bold]{len(rows)}[/bold] 条用例行")

    cfg = load_config(config_path)
    llm_cfg = cfg.judges.llm
    if enrich and not llm_cfg.enabled:
        console.print(
            "[yellow]config.judges.llm.enabled=false，将跳过 LLM 富化（等同 --no-enrich）[/yellow]"
        )
        enrich = False

    enrichments = []
    parsed_list: list[list[dict[str, Any]] | None] = []
    report_entries: list[dict[str, Any]] = []

    for row in rows:
        parsed = (
            parse_scoring_points(row.scoring_points_text)
            if row.scoring_points_text.strip()
            else None
        )
        parsed_list.append(parsed)

        enrich_result = None
        mode = "skeleton"
        needs_review = False

        if row.round_count_declared is not None and row.round_count_declared != len(
            row.rounds
        ):
            needs_review = True

        if enrich:
            try:
                enrich_result = enrich_case_fields(
                    row, llm_cfg=llm_cfg, id_prefix=id_prefix
                )
                mode = enrich_result.mode
            except Exception as exc:  # noqa: BLE001
                log.exception("LLM enrich failed for row %s", row.row_index)
                console.print(
                    f"[red]第 {row.row_index} 行 LLM 富化失败:[/red] {exc}"
                )
                return 1
        else:
            if not parsed:
                needs_review = True

        enrichments.append(enrich_result)
        report_entries.append(
            {
                "row_index": row.row_index,
                "mode": mode,
                "has_sheet_scoring_points": bool(parsed),
                "rounds": len(row.rounds),
                "round_count_declared": row.round_count_declared,
                "needs_review": needs_review,
            }
        )

    cases = rows_to_cases(
        rows,
        id_prefix=id_prefix,
        enrichments=enrichments,
        parsed_points_list=parsed_list,
    )

    if dry_run:
        for case in cases[:3]:
            console.print(yaml.safe_dump(
                [case.model_dump(mode="json", exclude={"case_file"})],
                allow_unicode=True,
                sort_keys=False,
            ))
        if len(cases) > 3:
            console.print(f"... 另有 {len(cases) - 3} 条")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    payload = [c.model_dump(mode="json", exclude={"case_file"}) for c in cases]
    out.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    report_path = out.with_suffix(out.suffix + ".import_report.json")
    _write_import_report(report_path, report_entries)

    console.print(f"[green]已写入[/green] {out} ({len(cases)} 条)")
    console.print(f"[green]报告[/green] {report_path}")

    if skip_validate:
        return 0

    base_dir = config_path.resolve().parent
    try:
        rel_out = out.resolve().relative_to(base_dir)
    except ValueError:
        rel_out = out
    from ..loader import load_cases

    try:
        loaded = load_cases(include=[str(rel_out)], base_dir=base_dir)
        console.print(f"[green]用例 schema 校验通过（{len(loaded)} 条）[/green]")
    except Exception as exc:
        console.print(f"[red]用例校验失败:[/red] {exc}")
        return 1
    return 0


@click.command("import-feishu")
@click.option(
    "--sheet-url",
    required=True,
    help="飞书电子表格 URL（/sheets/shtcn...）",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(path_type=Path),
    required=True,
    help="输出 YAML 路径",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default="config.yaml",
    show_default=True,
)
@click.option("--worksheet", default=None, help="工作表标题（默认第一个 sheet）")
@click.option("--id-prefix", default="imp_", show_default=True, help="sample_id 前缀")
@click.option("--enrich/--no-enrich", default=True, help="是否调用 LLM 补全判据")
@click.option("--skip-validate", is_flag=True, help="跳过 validate")
@click.option("--dry-run", is_flag=True, help="只打印前几条，不写文件")
def import_feishu_cmd(
    sheet_url: str,
    out_path: Path,
    config_path: Path,
    worksheet: str | None,
    id_prefix: str,
    enrich: bool,
    skip_validate: bool,
    dry_run: bool,
) -> None:
    """从飞书电子表格导入 benchmark 并生成 TestCase YAML。"""
    raise SystemExit(
        run_import(
            sheet_url=sheet_url,
            out=out_path,
            config_path=config_path,
            worksheet=worksheet,
            id_prefix=id_prefix,
            enrich=enrich,
            skip_validate=skip_validate,
            dry_run=dry_run,
        )
    )
