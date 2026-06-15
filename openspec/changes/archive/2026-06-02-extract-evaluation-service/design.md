# Design — 抽取评测服务层

## 分层原则：功能核 / 命令式外壳

- **功能核**（`service.evaluate`）：纯编排，唯一副作用是 adapter 网络调用。输入 typed `Config` + cases + 注入的 adapter/judges/adjudicator，输出 `RunReport`。无 console / 无 click / 无 sys.exit / 无文件写盘。
- **持久化层**（`service.write_core_artifacts` / `resolve_diff_target`）：文件副作用集中、可在 tmp 目录测、无网络、无 console。
- **命令式外壳**（`cli.run`）：flag 解析、config 加载/覆盖、dry-run、进度条、总览打印、飞书发布、阈值断言 + 退出码。把上面几层串起来并注入副作用实现。

## `medeval/service.py` 表面

```python
class ProgressObserver(Protocol):
    def start_phase(self, key: str, label: str, total: int) -> None: ...
    def advance(self, key: str, n: int = 1) -> None: ...

class NullProgress:  # 默认 no-op，SDK 不传即用它
    def start_phase(self, key, label, total): ...
    def advance(self, key, n=1): ...

def build_judges(judges_cfg: JudgesCfg) -> list: ...
def build_adjudicator(judges_cfg: JudgesCfg) -> SemanticRuleAdjudicator | None: ...

async def evaluate(
    config: Config, cases: list[TestCase],
    adapter, judges: list, adjudicator,
    *, progress: ProgressObserver = NullProgress(),
) -> RunReport: ...

def resolve_diff_target(diff_target: str, outputs_dir: Path, out_dir: Path) -> Path | None: ...

@dataclass
class Artifacts:
    report_json: Path
    diff_summary: str
    transcripts_path: Path

def write_core_artifacts(report: RunReport, out_dir: Path, *, prev_json: Path | None) -> Artifacts: ...

def _find_previous_run(outputs_dir: Path, current_dir: Path) -> Path | None: ...  # 迁自 cli
```

phase key 固定：`"run"`（调 chatbot）/ `"judge_det"`（确定性）/ `"judge_llm"` / `"judge_sp"`（得分点）。

## evaluate 内部 = 原 `_go` 全流程（逻辑逐行搬运，不改）

1. 拆 deterministic vs llm/scoring_point judges。
2. `progress.start_phase("run", "调用 chatbot", len(cases)*n_runs)`；`run_cases(..., on_progress=lambda *_: progress.advance("run"))`，并发/超时/重试取 `config.run.*`，`repeat=config.run.repeat`。
3. `progress.start_phase("judge_det", ...)`；跨 case 并发跑确定性判分 + adjudicator（同一 case 内逐 run 顺序，保 stability 口径），`Semaphore(config.run.concurrency)`。
4. `fold_n_runs(...)`。
5. 有 llm judge：`start_phase("judge_llm", ...)` + 并发对代表 trace 跑一次、补 fingerprint。
6. 有 scoring_point judge：`start_phase("judge_sp", ...)` + 并发跑、派生 guideline_match_rate。
7. 软分重算（`llm.*` + `scoring_point.summary`）。
8. `await adapter.close()`。
9. `build_report(run_name=make_run_slug(config.run.name), results=folded, adapter_type=config.adapter.type, config_snapshot=config.model_dump(mode="json"), description=config.run.description, started_at, n_runs=config.run.repeat)`。

`started_at`：`evaluate` 内部取 `datetime.utcnow()`（与现状一致：现状在 `asyncio.run(_go())` 前取，差异仅毫秒级、不影响行为语义）。

## CLI 注入实现

- `RichProgress`（cli 内）实现 `ProgressObserver`：`start_phase` → `Progress.add_task` 存 key→task_id；`advance` → `Progress.update(task_id, advance=n)`。在 `with Progress(...) as progress:` 上下文里把它传给 `evaluate`。
- `--repeat` 覆盖：CLI 解析后写回 `config.run.repeat`，`evaluate` 只读 `config.run.repeat`（单一来源）。
- adapter 仍由 CLI `build_adapter(config.adapter.type, config.adapter.model_dump())` 构造后注入 → 现有测试 monkeypatch `medeval.cli.build_adapter` 不破。
- 时序依赖（markdown 嵌 sheet URL）：CLI 顺序 = `write_core_artifacts` → 打印 diff 状态 → 发 sheet 拿 url → `write_markdown(嵌 url)` → 发 doc。`write_core_artifacts` 不写 md。

## 不做的事

- 不改判分/折叠/报告任何逻辑（行为零变化）。
- 不把飞书发布/console/退出码移入服务层（保持外壳职责）。
- 不引入 class 状态机；服务层用模块级函数 + 注入。

## 测试（TDD）

`tests/test_service.py`：
- `evaluate`：stub adapter（返回固定 reply）+ HardGate/Rule judges + 1 个最小 case + `NullProgress` → 得 `RunReport`，断言 total/passed/n_runs 等；记录式 observer 断言收到 `run`/`judge_det` 的 start_phase+advance。
- `resolve_diff_target`：`none`/`off`→None；具体名→`outputs/<name>/report.json`（存在）；不存在→None；`auto`/空→上一次。
- `write_core_artifacts`：tmp out_dir 写出 `report.json` + `transcripts.xlsx`；`prev_json=None` → `diff_summary==""`；给一个 prev report.json → `diff_summary` 非空。
- 现有 e2e（`test_report_formats_default`）回归绿。
- 全量 pytest + `verify-heuristics` + 真实 1-case run 行为对拍。
