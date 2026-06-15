"""CLI 层 rejudge / prune 冒烟测试（change 2026-06-04-persist-traces-rejudge）。

不触网：config 关闭 llm / scoring_point / semantic_adjudicator / lark，
仅 hard_gate + rule 离线判分。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from click.testing import CliRunner

from medeval.adapter.base import BaseAdapter, ChatResponse
from medeval.cli import main
from medeval.config import load_config
from medeval.models import Level, TestCase, Turn
from medeval.service import build_judges, evaluate, write_core_artifacts

_CONFIG = """
run:
  name: clitest
  output_dir: outputs
  concurrency: 2
  timeout_s: 5
  retry: 0
  persist_traces: true
  store_raw: on_error
  retention:
    enabled: true
    keep_last: 1
adapter:
  type: openai_compat
  openai_compat:
    base_url: "http://x"
    model: m
    system_prompt: p
judges:
  hard_gates: {enabled: true}
  rule: {enabled: true}
  llm: {enabled: false}
  scoring_point: {enabled: false}
reporter:
  lark: {enabled: false}
"""


class _StubAdapter(BaseAdapter):
    name = "stub"

    async def chat(self, req) -> ChatResponse:
        return ChatResponse(
            reply="建议尽快就医，若情况严重请立即拨打 120。本回答仅供参考，不能替代医生面诊。",
            raw={"x": 1},
        )

    async def close(self):
        pass


def _seed_run(base: Path, slug: str) -> Path:
    """用 stub adapter 造一个含 report.json + traces.jsonl.gz 的 run 目录。"""
    cfg = load_config(base / "config.yaml")
    cases = [TestCase(sample_id="c0", scenario="s", level=Level.L2, turns=[Turn(content="q")])]
    judges = build_judges(cfg.judges)
    out_dir = base / "outputs" / slug
    report = asyncio.run(
        evaluate(cfg, cases, _StubAdapter(), judges, None, run_name=slug, out_dir=out_dir)
    )
    write_core_artifacts(report, out_dir, prev_json=None)
    return out_dir


def test_cli_rejudge_creates_new_run(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as fs:
        base = Path(fs)
        (base / "config.yaml").write_text(_CONFIG, encoding="utf-8")
        seed = _seed_run(base, "clitest_seed")
        assert (seed / "traces.jsonl.gz").exists()

        result = runner.invoke(main, ["rejudge", str(seed), "--config", "config.yaml"])
        assert result.exit_code == 0, result.output
        # 产出新 run 目录（区别于 seed）
        run_dirs = [d for d in (base / "outputs").iterdir() if (d / "report.json").is_file()]
        assert len(run_dirs) == 2
        new_dir = next(d for d in run_dirs if d.name != "clitest_seed")
        assert (new_dir / "report.json").exists()
        assert (new_dir / "report.md").exists()


def test_cli_prune_dry_run_keeps_files(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as fs:
        base = Path(fs)
        (base / "config.yaml").write_text(_CONFIG, encoding="utf-8")
        outputs = base / "outputs"
        # 造两个含胖产物的 run
        for name in ["r1", "r2"]:
            d = outputs / name
            d.mkdir(parents=True)
            (d / "report.json").write_text("{}", encoding="utf-8")
            (d / "traces.jsonl.gz").write_bytes(b"x")

        # dry-run：keep_last=1 会"将清理"最旧者，但不真删
        result = runner.invoke(main, ["prune", "--config", "config.yaml", "--keep-last", "1", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert (outputs / "r1" / "traces.jsonl.gz").exists()
        assert (outputs / "r2" / "traces.jsonl.gz").exists()

        # 实跑：删最旧者胖产物，report.json 保留
        result2 = runner.invoke(main, ["prune", "--config", "config.yaml", "--keep-last", "1"])
        assert result2.exit_code == 0, result2.output
        remaining = sum(
            1 for n in ["r1", "r2"] if (outputs / n / "traces.jsonl.gz").exists()
        )
        assert remaining == 1
        assert (outputs / "r1" / "report.json").exists()
        assert (outputs / "r2" / "report.json").exists()
