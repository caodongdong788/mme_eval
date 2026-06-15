## ADDED Requirements

### Requirement: Runner 必须采集每轮与整段会话耗时

runner 在每次调用 adapter 取得 bot 回复时 MUST 用单调时钟（`time.perf_counter`）测量该轮端到端耗时，并 MUST 将逐轮耗时写入 `ConversationTrace.turn_latencies_ms`；整段会话总耗时 MUST 复用既有的 `ConversationTrace.duration_ms`（已由 runner 填充）。新增字段 MUST 带默认值（空列表）以兼容历史 `report.json`，且 MUST NOT 参与任何判分或 `overall_passed` 计算。

#### Scenario: 多轮会话记录逐轮与总耗时

- **WHEN** 一条三轮用例被执行
- **THEN** `ConversationTrace.turn_latencies_ms` MUST 含 3 个非负逐轮耗时，`duration_ms` MUST 为非负总耗时

#### Scenario: 延迟字段不影响判分

- **WHEN** 同一条 trace 在引入延迟采集前后分别判分
- **THEN** `overall_passed` 与各 judge verdict MUST 完全一致

### Requirement: N-runs 下必须逐次记录会话总耗时且错误 run 不计入聚合

在 N-runs 模式下，`CaseResult` MUST 以 `per_run_latency_ms` 逐次记录每次会话总耗时（N=1 时长度为 1）。`RunReport` MUST 聚合延迟统计（至少 平均、中位、P90、最大，单位 ms）。`trace.error` 非空的 run MUST NOT 计入 `RunReport` 的延迟聚合（避免超时把统计带偏）。

#### Scenario: N=3 逐次记录

- **WHEN** 一条用例 repeat=3 且三次均成功
- **THEN** `per_run_latency_ms` 长度 MUST 为 3，`RunReport.latency_summary` MUST 含 avg/median/p90/max

#### Scenario: 错误 run 不计入聚合

- **WHEN** 某次 run 因 adapter 三次重试失败导致 `trace.error` 非空
- **THEN** 该次耗时 MUST NOT 进入 `RunReport` 的延迟聚合统计
