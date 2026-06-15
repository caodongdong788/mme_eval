"""Test trim-report-formats: html 下线 / json 始终写 / 飞书默认开 / formats 校验。

完整 e2e 用 click CliRunner 跑一遍 medeval run，靠真实 case + FakeAdapter
简化判分。无网络依赖。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from medeval.cli import main


ROOT = Path(__file__).resolve().parent.parent


def _write_minimal_case_dir(tmp_path: Path) -> Path:
    """在 tmp_path 内写一个自包含的最小合法用例目录。

    刻意不依赖仓库 `cases/` 的任何具体路径（历史上曾硬编码已删除的
    `cases/L1_medical_knowledge`，用例库重组后即整片失败）。自带 fixture 让这些
    e2e 用例成为稳定回归基线，只验证 reporter 写盘路径、与用例库布局解耦。
    """
    case_dir = tmp_path / "min_cases"
    case_dir.mkdir(parents=True, exist_ok=True)
    case = {
        "sample_id": "e2e_min_case",
        "scenario": "e2e_test",
        "level": "L1",
        "turns": [{"role": "user", "content": "我最近有点担心健康问题，能给点建议吗"}],
        "hard_gates": {
            "red_flag_triage": "none",
            "no_prescription": True,
            "require_disclaimer": False,
        },
    }
    (case_dir / "min_case.yaml").write_text(
        yaml.safe_dump(case, allow_unicode=True), encoding="utf-8"
    )
    return case_dir


def _write_minimal_config(
    tmp_path: Path,
    formats: list[str] | None,
    lark_enabled: bool | None,
    *,
    run_name: str,
) -> Path:
    """造一个最小配置：1 个自带的最小 case + http adapter（仅测 reporter 写盘路径）。

    用 stub adapter（见各测试内的 monkeypatch）跑出 ≥1 条结果，reporter 按 formats
    规则写 report.md/json。case fixture 自包含于 tmp_path，不耦合仓库用例库布局。
    """
    case_dir = _write_minimal_case_dir(tmp_path)
    cfg = {
        "run": {
            "name": run_name,
            "output_dir": str(tmp_path / "outputs"),
            "concurrency": 1,
            "timeout_s": 5,
            "retry": 0,
            "repeat": 1,
        },
        "cases": {
            "include": [str(case_dir)],
            "exclude": [],
            "score_profiles": [],
        },
        "adapter": {
            "type": "http",
            "http": {"base_url": "http://localhost:9", "endpoint": "/x"},
        },
        "judges": {
            "hard_gates": {"enabled": True},
            "rule": {"enabled": True, "normalize": True},
            "llm": {"enabled": False},
        },
        "reporter": {
            "lark": {"enabled": lark_enabled} if lark_enabled is not None else {},
        },
        "thresholds": {
            "hard_gate_pass_rate": 0.0,
            "l3_red_flag_pass_rate": 0.0,
            "overall_pass_rate": 0.0,
            "l2_business_pass_rate": 0.0,
            "l4_adversarial_pass_rate": 0.0,
        },
    }
    if formats is not None:
        cfg["reporter"]["formats"] = formats
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return cfg_path


def _resolve_out_dir(tmp_path: Path, run_name: str) -> Path:
    """定位本次评测的实际输出目录。

    CLI 把结果落到 `outputs/<run.name>_<YYYY-MM-DD>_<毫秒时间戳>/`（独立目录、不覆盖历史），
    因此测试不能硬编码完整目录名，需按 `run.name` 前缀匹配出唯一目录。
    """
    outputs = tmp_path / "outputs"
    matches = sorted(outputs.glob(f"{run_name}_*"))
    assert len(matches) == 1, f"expected exactly one run dir for {run_name!r}, got {matches}"
    return matches[0]


def test_formats_html_is_rejected(tmp_path: Path):
    """formats 含 'html' 必须立即 fail-fast。"""
    cfg_path = _write_minimal_config(
        tmp_path, formats=["html"], lark_enabled=False, run_name="reject_html"
    )
    runner = CliRunner()
    result = runner.invoke(main, ["run", "--config", str(cfg_path), "--dry-run"])
    assert result.exit_code != 0
    # dry-run 不会触达 reporter，所以 html 校验需要在跑完后；改成不带 dry-run
    result = runner.invoke(main, ["run", "--config", str(cfg_path), "--limit", "1"])
    assert result.exit_code != 0
    output = result.output + (result.stderr if hasattr(result, "stderr") else "")
    assert "html" in output.lower() and (
        "下线" in output or "trim-report-formats" in output
    )


def test_default_outputs_md_and_json(tmp_path: Path, monkeypatch):
    """默认配置（formats 缺失）应当产出 report.md + report.json，无 report.html。"""
    # 用真正可工作的 _FakeAdapter：通过临时注入到 medeval.adapter 工厂
    from medeval.adapter import build_adapter as real_build
    from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse

    class _Stub(BaseAdapter):
        name = "stub"

        async def chat(self, req: ChatRequest) -> ChatResponse:
            return ChatResponse(
                reply="若情况严重请立即拨打 120 急诊，本回答仅供参考不能替代医生面诊", raw={}
            )

        async def close(self):
            pass

    def fake_build(adapter_type, config):
        if adapter_type == "http":
            return _Stub()
        return real_build(adapter_type, config)

    monkeypatch.setattr("medeval.cli.build_adapter", fake_build)

    cfg_path = _write_minimal_config(
        tmp_path, formats=None, lark_enabled=False, run_name="default_outputs"
    )
    runner = CliRunner()
    # --limit 2 只跑两条，加速
    result = runner.invoke(
        main, ["run", "--config", str(cfg_path), "--limit", "2"]
    )
    assert result.exit_code == 0, result.output

    out_dir = _resolve_out_dir(tmp_path, "default_outputs")
    assert (out_dir / "report.md").exists(), "expected report.md"
    assert (out_dir / "report.json").exists(), "expected report.json"
    assert not (out_dir / "report.html").exists(), "report.html 不应再被生成"

    # JSON 内容必须含新字段
    data = json.loads((out_dir / "report.json").read_text())
    assert "n_runs" in data
    assert "stability_distribution" in data


def test_empty_formats_still_writes_json(tmp_path: Path, monkeypatch):
    """formats: [] 时 json 仍写、md 不写。"""
    from medeval.adapter import build_adapter as real_build
    from medeval.adapter.base import BaseAdapter, ChatRequest, ChatResponse

    class _Stub(BaseAdapter):
        name = "stub"

        async def chat(self, req):
            return ChatResponse(
                reply="若情况严重请立即拨打 120 急诊，本回答仅供参考", raw={}
            )

        async def close(self):
            pass

    monkeypatch.setattr(
        "medeval.cli.build_adapter",
        lambda t, c: _Stub() if t == "http" else real_build(t, c),
    )

    cfg_path = _write_minimal_config(
        tmp_path, formats=[], lark_enabled=False, run_name="empty_fmt"
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["run", "--config", str(cfg_path), "--limit", "1"]
    )
    assert result.exit_code == 0, result.output
    out_dir = _resolve_out_dir(tmp_path, "empty_fmt")
    assert (out_dir / "report.json").exists(), "JSON 应始终写"
    assert not (out_dir / "report.md").exists(), "formats 为空时 md 不写"


def test_json_in_formats_is_warned_and_ignored(tmp_path: Path, monkeypatch, capsys):
    """formats 含 'json' 必须 warning + 忽略，不影响实际输出。"""
    from medeval.adapter import build_adapter as real_build
    from medeval.adapter.base import BaseAdapter, ChatResponse

    class _Stub(BaseAdapter):
        name = "stub"

        async def chat(self, req):
            return ChatResponse(reply="拨打 120", raw={})

        async def close(self):
            pass

    monkeypatch.setattr(
        "medeval.cli.build_adapter",
        lambda t, c: _Stub() if t == "http" else real_build(t, c),
    )
    cfg_path = _write_minimal_config(
        tmp_path,
        formats=["json", "markdown"],
        lark_enabled=False,
        run_name="json_warn",
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["run", "--config", str(cfg_path), "--limit", "1"]
    )
    assert result.exit_code == 0, result.output
    assert "json" in result.output.lower() and "ignored" in result.output.lower() or (
        "始终写盘" in result.output
    )
    out_dir = _resolve_out_dir(tmp_path, "json_warn")
    assert (out_dir / "report.md").exists()
    assert (out_dir / "report.json").exists()
