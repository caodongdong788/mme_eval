# observability Specification (delta)

## MODIFIED Requirements

### Requirement: 被测 bot 全链路 Langfuse 追踪

系统 MUST 提供面向**被测 bot** 的 Langfuse 追踪能力，软依赖、no-op 兜底：未安装 `langfuse` 可选依赖或 `observability.langfuse.enabled=false` 时，追踪调用 MUST 为零开销空操作，SHALL NOT 抛出导入错误或影响主链路。该能力 MUST 默认开启（`observability.langfuse.enabled` 默认 `true`），自托管地址（`base_url`/host）与凭据 MUST 仅从环境变量读取（MUST NOT 写入配置快照或留痕产物）；缺凭据/未装 SDK/初始化失败时 MUST 自动退化为 no-op。

启用时，**每条用例的每次执行（case/run）MUST 成为一条独立的 Langfuse trace**，其 `session_id` MUST 设为 `run_name`（使同一 run 的所有用例在 Langfuse 归入同一 session 可整体回放）；被测 bot 的每个 user turn 的 `adapter.chat` 调用 MUST 在该 trace 下产生一个 generation，携带 input(messages)/output(reply)/model/token usage/latency/error。系统 MUST 为每条用例捕获其 trace 深链（trace_id → trace_url，自动带 project_id、用自托管 base_url 拼链），并落到 `ConversationTrace.langfuse_trace_url`（随代表 trace 进入报告）；追踪关闭/未配置时该值 MUST 为 `None`。追踪 MUST NOT 改变任何判分结果、评分口径或控制流，任何追踪内部异常 MUST 被静默吞掉。judge 的 LLM 调用 MUST NOT 被追踪。

#### Scenario: 默认开启但未配置时优雅降级

- **WHEN** `observability.langfuse.enabled=true`（默认）但环境变量未提供凭据/host，或未安装 `langfuse`
- **THEN** 评测 MUST 正常执行、不产生追踪、不报错，且每条用例的 `langfuse_trace_url` MUST 为 `None`

#### Scenario: 启用时每条用例一条 trace 并捕获深链

- **WHEN** 已安装 `langfuse` 且凭据/host 齐备、`enabled=true`
- **THEN** 每条 case/run MUST 是一条独立 trace（`session_id=run_name`），其下每个 user turn MUST 产生带 input/output/model/usage/latency 的 generation，且该用例的 `langfuse_trace_url` MUST 为可打开的自托管深链；评测结果 MUST 与关闭追踪时完全一致

#### Scenario: 未安装依赖仍可运行

- **WHEN** 运行环境未安装 `langfuse` 可选依赖
- **THEN** 导入与运行 MUST 不报错，追踪自动退化为 no-op

#### Scenario: judge 调用不被追踪

- **WHEN** 追踪启用且 LLM-as-Judge 正在判分
- **THEN** judge 的 LLM 调用 MUST NOT 产生 Langfuse generation
