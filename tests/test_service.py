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
from medeval.evaluation import EvaluationDimension
from medeval.models import JudgeVerdict, Level, TestCase, Turn, RunReport
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
                "eight_dimension": {"enabled": False},
                "guideline": {"enabled": False},
            },
        }
    )


def _case() -> TestCase:
    return TestCase(
        schema_version="2.0",
        sample_id="svc_case",
        scenario="svc",
        level=Level.L2,
        turns=[Turn(role="user", content="我最近有点担心健康问题")],
        evaluation={},
    )


def _run_evaluate(progress=None):
    config = _config()
    cases = [_case()]
    judges = build_judges(config.judges)
    return asyncio.run(
        evaluate(config, cases, _StubAdapter(), judges, progress=progress)
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
    assert phase_keys == ["run"]
    assert rec.advances.get("run") == 1


def test_evaluate_declares_phase_plan_upfront():
    # 开跑前应一次性声明完整阶段计划，供前端算全局单调进度。
    rec = _RecordingProgress()
    _run_evaluate(progress=rec)
    assert rec.plan is not None
    plan_keys = [k for k, _label, _total in rec.plan]
    assert plan_keys == ["run"]
    # 计划总量为正
    assert all(total > 0 for _k, _l, total in rec.plan)


def test_evaluate_notifies_completed_case_before_full_run_finishes():
    class StagedAdapter(_StubAdapter):
        def __init__(self, slow_case_gate: asyncio.Event):
            self.slow_case_gate = slow_case_gate

        async def chat(self, req) -> ChatResponse:
            user_text = [message["content"] for message in req.messages if message["role"] == "user"][-1]
            if user_text == "慢用例":
                await self.slow_case_gate.wait()
            return await super().chat(req)

    async def scenario() -> None:
        config = _config()
        fast = _case().model_copy(update={"sample_id": "fast", "turns": [Turn(role="user", content="快用例")]})
        slow = _case().model_copy(update={"sample_id": "slow", "turns": [Turn(role="user", content="慢用例")]})
        completed = asyncio.Event()
        slow_case_gate = asyncio.Event()

        class CompletionProgress(_RecordingProgress):
            async def case_completed(self, result):
                seen.append(result.case.sample_id)
                completed.set()

        seen: list[str] = []
        task = asyncio.create_task(
            evaluate(
                config,
                [fast, slow],
                StagedAdapter(slow_case_gate),
                [],
                progress=CompletionProgress(),
            )
        )
        await asyncio.wait_for(completed.wait(), timeout=1)
        assert seen == ["fast"]
        assert not task.done()
        slow_case_gate.set()
        report = await task
        assert report.total == 2

    asyncio.run(scenario())


def test_evaluate_reruns_entire_case_once_after_judge_error():
    """Judge 异常时必须重跑 Agent 对话，而不是只重判旧 trace。"""

    class CountingAdapter(_StubAdapter):
        def __init__(self):
            self.calls = 0

        async def chat(self, req) -> ChatResponse:
            self.calls += 1
            return await super().chat(req)

    class FlakyDimensionJudge:
        name = "dimension"

        def __init__(self):
            self.calls = 0

        def fingerprint(self) -> str:
            return "test-flaky-dimension"

        async def judge(self, case, trace):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary judge outage")
            return [
                JudgeVerdict(
                    name=f"dimension.{dimension.value}",
                    passed=True,
                    score=5,
                    max_score=5,
                )
                for dimension in EvaluationDimension
            ]

    async def scenario() -> None:
        adapter = CountingAdapter()
        judge = FlakyDimensionJudge()
        report = await evaluate(_config(), [_case()], adapter, [judge])
        assert adapter.calls == 2
        assert judge.calls == 2
        assert report.results[0].judge_error is False
        assert report.results[0].grade != "判分异常"

    asyncio.run(scenario())


def test_evaluate_stops_after_one_full_case_retry_when_judge_keeps_failing():
    class CountingAdapter(_StubAdapter):
        def __init__(self):
            self.calls = 0

        async def chat(self, req) -> ChatResponse:
            self.calls += 1
            return await super().chat(req)

    class BrokenJudge:
        name = "dimension"

        def fingerprint(self) -> str:
            return "test-broken-dimension"

        async def judge(self, case, trace):
            raise RuntimeError("persistent judge outage")

    async def scenario() -> None:
        adapter = CountingAdapter()
        report = await evaluate(_config(), [_case()], adapter, [BrokenJudge()])
        assert adapter.calls == 2
        assert report.results[0].judge_error is True
        assert report.results[0].grade == "判分异常"

    asyncio.run(scenario())


def test_evaluate_retries_full_case_once_when_judge_exhausts_case_budget():
    """Judge 超过单题预算后，应从头重跑一次完整 Agent 对话。"""

    class CountingAdapter(_StubAdapter):
        def __init__(self):
            self.calls = 0

        async def chat(self, req) -> ChatResponse:
            self.calls += 1
            return await super().chat(req)

    class SlowThenHealthyJudge:
        name = "dimension"

        def __init__(self):
            self.calls = 0

        def fingerprint(self) -> str:
            return "test-slow-then-healthy"

        async def judge(self, case, trace):
            self.calls += 1
            if self.calls == 1:
                await asyncio.sleep(0.08)
            return [
                JudgeVerdict(
                    name=f"dimension.{dimension.value}",
                    passed=True,
                    score=5,
                    max_score=5,
                )
                for dimension in EvaluationDimension
            ]

    async def scenario() -> None:
        config = _config()
        config.run.case_timeout_s = 0.04
        adapter = CountingAdapter()
        judge = SlowThenHealthyJudge()
        report = await evaluate(config, [_case()], adapter, [judge])
        assert adapter.calls == 2
        assert judge.calls == 2
        assert report.results[0].judge_error is False

    asyncio.run(scenario())


def test_evaluate_records_judge_timeout_after_second_case_attempt():
    """两次判分都耗尽预算时必须生成“判分异常”，不能让整条任务无结果。"""

    class CountingAdapter(_StubAdapter):
        def __init__(self):
            self.calls = 0

        async def chat(self, req) -> ChatResponse:
            self.calls += 1
            return await super().chat(req)

    class AlwaysSlowJudge:
        name = "dimension"

        def fingerprint(self) -> str:
            return "test-always-slow"

        async def judge(self, case, trace):
            await asyncio.sleep(0.08)
            return []

    async def scenario() -> None:
        config = _config()
        config.run.case_timeout_s = 0.04
        adapter = CountingAdapter()
        report = await evaluate(config, [_case()], adapter, [AlwaysSlowJudge()])
        assert adapter.calls == 2
        assert report.results[0].judge_error is True
        assert report.results[0].grade == "判分异常"

    asyncio.run(scenario())


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
