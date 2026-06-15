## Why

`overall_passed` 这一个布尔字段在数据流里被**三处各自赋值、且语义各不相同**：

1. `judges/aggregator.py`：`hard_gate AND rule AND no-error`（judging 层正确性）
2. `runner/voting.py`：majority voting 覆写
3. `reporter/scoring.py::apply_grading`：按 `pass_rule`（composite 满分 / threshold）再次覆写

报告里所有「通过率」建立在第 3 层口径上，而 `stability` 三态建立在第 1 层口径上——同名字段背两种语义，跨层调试极易踩坑，README 也只能用脚注解释「评级≠通过、可良好却 overall_passed=False」。

此外存在两处隐患：
- **双套真值**：`aggregator._summarize_verdicts`（gate 布尔）与 `scoring.score_case`（加权分）各自遍历一遍 verdicts、各自解释，口径可能漂移。
- **LLM/得分点判分无确定性保护**：N-runs voting 只覆盖确定性 judge，最吵的 LLM 维度只在代表性 trace 上裸跑一次。
- **判分阶段全串行**：`cli._go` 的确定性 judge / adjudicator / LLM / scoring_point 四阶段都是 `for ... await`，墙钟时间浪费明显。

研发阶段，**不考虑历史 report.json 兼容**：字段可直接重命名、不写回填逻辑、diff 只认新字段。

## What Changes

- **拆字段并收敛单一赋值点**（口径解耦）：
  - `CaseResult.overall_passed` → `release_passed`（上线判定，唯一赋值点 = `apply_grading`）
  - 新增 `CaseResult.gate_passed`（judging 层 per-run 正确性，唯一赋值点 = `aggregator`）
  - `CaseResult.per_run_passed` → `per_run_gate_passed`
  - `voting.fold_n_runs` 的 majority / stability 全部基于 `gate_passed`，不再借用 release 口径
- **单一 verdict→facts 提取**（消除双套真值）：新增 `DerivedFacts` + `verdict_facts(...)`，`_summarize_verdicts` 与 `score_case` 共用同一遍历结果。
- **LLM/得分点 self-consistency**：`judges.llm` / `judges.scoring_point` 新增 `self_consistency`（默认 1=零成本）与 `aggregate`（min/median）；K>1 时对同一代表 trace 调 K 次并聚合，产出判分离散度（仅观测、不否决）。
- **判分阶段并发化**：`cli._go` 四阶段由串行改为 `Semaphore + asyncio.gather`。

## Capabilities

### Modified Capabilities
- `judging-pipeline`：Aggregator 计算的 per-run 正确性字段由 `overall_passed` 更名为 `gate_passed`；N-runs 折叠的 majority / stability / 逐 run 记录基于 `gate_passed`、字段更名为 `per_run_gate_passed`；LLM/得分点判官支持 self-consistency K 采样与离散度产出。
- `reporting`：报告层最终通过/失败口径字段由 `overall_passed` 更名为 `release_passed`（唯一赋值点 = `apply_grading`），并显式依赖 majority `gate_passed`；报告新增软分离散度展示（仅观测）。

## Impact

- 代码：`medeval/models.py`（字段重命名 + 新增 `gate_passed`、离散度字段）、`medeval/judges/aggregator.py`（`DerivedFacts` + `verdict_facts`，只写 `gate_passed`）、`medeval/judges/llm.py` + `scoring_point.py`（self-consistency）、`medeval/runner/voting.py`（基于 `gate_passed`）、`medeval/reporter/scoring.py`（唯一写 `release_passed`，消费 `DerivedFacts`）、`medeval/reporter/aggregator.py` / `markdown_report.py` / `diff.py` / `excel_transcript.py`（下游引用切换）、`medeval/cli.py`（并发化 + `_check_thresholds`）、`config.yaml`（self_consistency 字段）、`tests/`、`AGENTS.md` / `README.md`。
- 兼容性：研发阶段，**放弃历史 report.json 兼容**；不保留旧字段名、不写回填。
- 依赖：不引入新依赖。
