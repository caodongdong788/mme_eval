"""评测服务层单测（change 2026-06-02-extract-evaluation-service）。

覆盖：
  - evaluate：stub adapter（无网络）跑出 RunReport；记录式 observer 收到 phase 事件
  - resolve_diff_target：none/off / 具体名(存在/不存在) / auto
  - write_core_artifacts：tmp 写 report.json + transcripts.xlsx；prev 有无 → diff_summary
"""

from __future__ import annotations

import asyncio
import json

from medeval.adapter.base import BaseAdapter, ChatResponse
from medeval.config import parse_config
from medeval.models import Level, TestCase, Turn, RunReport
from medeval.service import (
    Artifacts,
    NullProgress,
    build_judges,
    evaluate,
    resolve_diff_target,
    write_core_artifacts,
)


class _StubAdapter(BaseAdapter):
    name = "stub"

    async def chat(self, req) -> ChatResponse:
        return ChatResponse(
            reply="建议尽快就医，若情况严重请立即拨打 120。本回答仅供参考，不能替代医生面诊。",
            raw={},
        )

    async def close(self):
        pass


class _RecordingProgress:
    def __init__(self):
        self.phases: list[tuple[str, str, int]] = []
        self.advances: dict[str, int] = {}
        self.plan: list[tuple[str, str, int]] | None = None

    def plan_phases(self, phases):
        self.plan = list(phases)

    def start_phase(self, key, label, total):
        self.phases.append((key, label, total))

    def advance(self, key, n=1):
        self.advances[key] = self.advances.get(key, 0) + n


def _config():
    return parse_config(
        {
            "run": {"name": "svc_test", "concurrency": 2, "timeout_s": 5, "retry": 0},
            "adapter": {
                "type": "openai_compat",
                "openai_compat": {"base_url": "http://x", "model": "m"},
            },
            "judges": {
                "hard_gates": {"enabled": True},
                "rule": {"enabled": True},
                "llm": {"enabled": False},
            },
        }
    )


def _case() -> TestCase:
    return TestCase(
        sample_id="svc_case",
        scenario="svc",
        level=Level.L2,
        turns=[Turn(role="user", content="我最近有点担心健康问题")],
    )


def _run_evaluate(progress=None):
    config = _config()
    cases = [_case()]
    judges = build_judges(config.judges)
    return asyncio.run(
        evaluate(config, cases, _StubAdapter(), judges, None, progress=progress)
    )


# --- evaluate --------------------------------------------------------------


def test_evaluate_returns_runreport_no_network():
    report = _run_evaluate()
    assert isinstance(report, RunReport)
    assert report.total == 1
    assert report.n_runs == 1
    assert len(report.results) == 1


def test_evaluate_default_null_progress_ok():
    # 不传 progress → NullProgress，正常完成无副作用
    report = _run_evaluate(progress=None)
    assert report.total == 1
    # 显式 NullProgress 亦可
    report2 = _run_evaluate(progress=NullProgress())
    assert report2.total == 1


def test_evaluate_reports_progress_phases():
    rec = _RecordingProgress()
    _run_evaluate(progress=rec)
    phase_keys = [p[0] for p in rec.phases]
    assert "run" in phase_keys
    assert "judge_det" in phase_keys
    # 1 case * 1 run 各推进一次
    assert rec.advances.get("run") == 1
    assert rec.advances.get("judge_det") == 1
    # 未启用 llm/scoring_point → 无对应阶段
    assert "judge_llm" not in phase_keys
    assert "judge_sp" not in phase_keys


def test_evaluate_declares_phase_plan_upfront():
    # 开跑前应一次性声明完整阶段计划，供前端算全局单调进度。
    rec = _RecordingProgress()
    _run_evaluate(progress=rec)
    assert rec.plan is not None
    plan_keys = [k for k, _label, _total in rec.plan]
    # 未启用 llm/scoring_point → 计划只含 run + judge_det
    assert plan_keys == ["run", "judge_det"]
    # 计划总量为正
    assert all(total > 0 for _k, _l, total in rec.plan)


# --- resolve_diff_target ---------------------------------------------------


def _make_run_dir(outputs, name):
    d = outputs / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.json").write_text("{}", encoding="utf-8")
    return d


def test_resolve_diff_target_none_off(tmp_path):
    outputs = tmp_path / "outputs"
    out_dir = _make_run_dir(outputs, "cur")
    assert resolve_diff_target("none", outputs, out_dir) is None
    assert resolve_diff_target("off", outputs, out_dir) is None


def test_resolve_diff_target_specific(tmp_path):
    outputs = tmp_path / "outputs"
    out_dir = _make_run_dir(outputs, "cur")
    _make_run_dir(outputs, "prev_v1")
    prev = resolve_diff_target("prev_v1", outputs, out_dir)
    assert prev == outputs / "prev_v1" / "report.json"
    # 不存在的指定版本 → None
    assert resolve_diff_target("nope", outputs, out_dir) is None


def test_resolve_diff_target_auto_picks_previous(tmp_path):
    outputs = tmp_path / "outputs"
    out_dir = _make_run_dir(outputs, "cur")
    other = _make_run_dir(outputs, "older")
    prev = resolve_diff_target("auto", outputs, out_dir)
    assert prev == other / "report.json"
    # 空字符串等价 auto
    assert resolve_diff_target("", outputs, out_dir) == other / "report.json"


# --- write_core_artifacts --------------------------------------------------


def test_write_core_artifacts_writes_json_and_transcripts(tmp_path):
    report = _run_evaluate()
    out_dir = tmp_path / "outputs" / "run1"
    arts = write_core_artifacts(report, out_dir, prev_json=None)
    assert isinstance(arts, Artifacts)
    assert arts.report_json.exists()
    assert arts.transcripts_path.exists()
    assert arts.diff_summary == ""  # 无 prev
    # report.json 内容可解析且含核心字段
    data = json.loads(arts.report_json.read_text())
    assert data["total"] == 1


def test_write_core_artifacts_diff_when_prev_given(tmp_path):
    report = _run_evaluate()
    # 先写一份作为 prev
    prev_dir = tmp_path / "outputs" / "prev"
    prev_arts = write_core_artifacts(report, prev_dir, prev_json=None)
    # 再写当前并对 prev diff
    cur_dir = tmp_path / "outputs" / "cur"
    arts = write_core_artifacts(report, cur_dir, prev_json=prev_arts.report_json)
    assert isinstance(arts.diff_summary, str)
    assert arts.diff_summary != ""  # 有 prev → 产出 diff 文本
