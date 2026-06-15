## ADDED Requirements

### Requirement: 评测全链路可选 OpenTelemetry tracing

系统 MUST 提供可选的 OpenTelemetry tracing 能力，默认关闭且以 no-op 实现兜底：未安装 `otel` 可选依赖或 `observability.otel.enabled=false` 时，tracing 调用 MUST 为零开销空操作，SHALL NOT 抛出导入错误或影响主链路。启用时，runner 每轮 adapter 调用、`evaluate` 各 phase（run/judge_det/judge_llm/judge_sp）、以及 LLM 与得分点 judge 调用 MUST 各产生一个 span，并携带可定位的属性（如 sample_id、turn_index、phase、latency、error）。tracing MUST NOT 改变任何判分结果、评分口径或控制流。

#### Scenario: 默认关闭时零开销

- **WHEN** `observability.otel.enabled=false`（默认）
- **THEN** 评测 MUST 正常执行且不产生任何 span，亦 MUST NOT 因缺少 otel 依赖而失败

#### Scenario: 启用时产生链路 span

- **WHEN** 已安装 otel 依赖且 `observability.otel.enabled=true`
- **THEN** runner 每轮 adapter 调用与 evaluate 各 phase MUST 产生带属性的 span，且评测结果 MUST 与关闭 tracing 时一致

#### Scenario: 未安装依赖仍可运行

- **WHEN** 运行环境未安装 `otel` 可选依赖
- **THEN** 导入与运行 MUST 不报错，tracing 自动退化为 no-op
