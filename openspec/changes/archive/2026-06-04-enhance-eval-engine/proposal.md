## Why

AgentScope 评测引擎有三项工程能力值得借鉴：用 bootstrap 把"通过率"呈现为带置信区间的统计分布（小样本/N-runs 下避免误导性单点值）、OpenTelemetry tracing（adapter/judge 全链路可观测）、Ray 分布式执行（大 benchmark 提速）。本期把这三项以**可选开关**形式落进 medeval 自己的引擎，**不引入 AgentScope 依赖、不改判分逻辑、不做轨迹评测**。默认配置下行为与现状完全一致。

## What Changes

- **统计**（reporting）：新增纯标准库 bootstrap 置信区间，`RunReport` 增 `pass_rate_ci`（基于 `release_passed`）；报告呈现误差区间。默认开启但纯报告层、零判分风险。
- **可观测性**（observability，新能力）：新增默认 no-op 的 tracing 层；装上可选 `otel` 依赖且显式开启时，runner 每轮 adapter 调用、`evaluate` 各 phase、LLM/得分点 judge 各发一个 span。默认关闭、不装 otel 也能正常运行。
- **规模化**（dialog-runner）：`run.executor` 支持 `local`（默认，现状逻辑原样）| `ray`；Ray 后端在 worker 内按 config 自建 adapter（规避 httpx client 不可序列化），产物结构与本地后端一致，使 `fold_n_runs`/judging/`build_report` 完全不变。

## Capabilities

### New Capabilities
- `observability`: 评测全链路 OpenTelemetry tracing（可选、默认关闭、no-op 兜底）。

### Modified Capabilities
- `reporting`: 报告 MUST 基于 `release_passed` 计算并呈现通过率 bootstrap 置信区间，且标注为统计估计。
- `dialog-runner`: 执行后端 MUST 可选 `local`/`ray`，两后端 MUST 产出结构一致的会话留痕，判分与折叠口径不受影响。

## Impact

- 代码：`medeval/reporter/stats.py`（新）、`medeval/observability/tracing.py`（新）、`medeval/runner/ray_backend.py`（新）、`medeval/models.py`（`RunReport` 增 CI 字段）、`medeval/config.py`（`RunCfg.executor`/`StatsCfg`/`ObservabilityCfg`）、`medeval/reporter/aggregator.py`、`medeval/reporter/markdown_report.py`、`medeval/runner/executor.py`、`medeval/service.py`、`frontend/`、`tests/`、`pyproject.toml`（`otel`/`ray` extras）。
- 兼容性：所有新增字段带默认值；新增开关默认值=现状（executor=local、otel 关闭）；历史 `report.json` 与现有判分行为完全不变；judge fingerprints 不变。
- 依赖：bootstrap 仅用标准库；`otel`/`ray` 为可选 extras，不装不影响主链路。
