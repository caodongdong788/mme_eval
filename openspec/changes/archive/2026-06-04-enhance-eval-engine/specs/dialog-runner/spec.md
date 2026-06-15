## ADDED Requirements

### Requirement: 执行后端可选 local 或 ray 且产物结构一致

dialog-runner MUST 支持通过 `run.executor` 选择执行后端：`local`（默认，单进程 asyncio 并发，逻辑与现状一致）或 `ray`（分布式）。`ray` 后端 MUST 在 worker 内按 adapter 配置自建 adapter 实例（规避持有网络 client 的 adapter 不可序列化问题），SHALL NOT 跨进程传递已建 adapter。两种后端 MUST 产出结构一致的 `list[list[ConversationTrace]]`（外层对齐用例顺序、内层长度等于 `repeat`），使后续 `fold_n_runs`、judging、`build_report` 完全不受后端选择影响。当选择 `ray` 但运行环境未安装 ray 时，系统 MUST 给出明确错误而非静默降级。

#### Scenario: 默认本地后端行为不变

- **WHEN** 配置未指定 `run.executor` 或取值为 `local`
- **THEN** 执行 MUST 走现状单进程并发路径，产物与本次变更前逐字段一致

#### Scenario: ray 后端产物结构对齐 local

- **WHEN** `run.executor=ray` 且 ray 可用
- **THEN** 返回的会话留痕结构 MUST 与 local 后端一致（外层=用例、内层=repeat），judging 与折叠口径 MUST NOT 改变

#### Scenario: 选择 ray 但未安装

- **WHEN** `run.executor=ray` 但环境未安装 ray
- **THEN** 系统 MUST 抛出清晰的配置/依赖错误，MUST NOT 悄悄回退到 local
