# observability Specification (delta)

## ADDED Requirements

### Requirement: 被测 bot 全链路 Langfuse 追踪

系统 MUST 提供可选的、面向**被测 bot** 的 Langfuse 追踪能力，默认关闭且以 no-op 兜底：未安装 `langfuse` 可选依赖或 `observability.langfuse.enabled=false`（默认）时，追踪调用 MUST 为零开销空操作，SHALL NOT 抛出导入错误或影响主链路。启用时，runner 每个 user turn 的 `adapter.chat` 调用 MUST 产生一个 Langfuse generation，携带可定位信息（input=messages、output=reply、model、token usage、latency、error）；每条 case/run MUST 包一个会话级 span，并嵌在以 `run_name` 命名的 run 级 root trace 下。追踪 MUST NOT 改变任何判分结果、评分口径或控制流，任何追踪内部异常 MUST 被静默吞掉。judge 的 LLM 调用本期 MUST NOT 被追踪。Langfuse 凭据 MUST 仅从环境变量读取，MUST NOT 写入配置快照或留痕产物。短命 CLI 进程收尾 MUST flush 以保证 trace 不丢。

#### Scenario: 默认关闭时零开销

- **WHEN** `observability.langfuse.enabled=false`（默认）
- **THEN** 评测 MUST 正常执行且不产生任何 Langfuse 追踪，亦 MUST NOT 因缺少 `langfuse` 依赖而失败

#### Scenario: 启用时产生 bot 链路 generation

- **WHEN** 已安装 `langfuse` 依赖且 `observability.langfuse.enabled=true`
- **THEN** 被测 bot 每个 user turn MUST 产生一个带 input/output/model/usage/latency 的 generation，会话 span MUST 嵌在 run 级 root trace 下，且评测结果 MUST 与关闭追踪时完全一致

#### Scenario: 未安装依赖仍可运行

- **WHEN** 运行环境未安装 `langfuse` 可选依赖
- **THEN** 导入与运行 MUST 不报错，Langfuse 追踪自动退化为 no-op

#### Scenario: judge 调用不被追踪

- **WHEN** 追踪启用且 LLM-as-Judge 正在判分
- **THEN** judge 的 LLM 调用 MUST NOT 产生 Langfuse generation
