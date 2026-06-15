# 多轮对话执行器（dialog-runner）

## Purpose

把"一条用例"实际跑成一段完整的多轮对话，并把所有交互证据（消息序列、原始响应、耗时、错误）落到 `ConversationTrace` 里。Runner 是评测框架中唯一与时间和并发打交道的层：它负责调度、超时控制、重试与去重；它对上层 Judge 暴露的只有一份纯静态的 `ConversationTrace`，因此 Judge 才能完全离线地做判分。

设计原则：

- **顺序内、并发外**：单条用例的 turns 必须严格按声明顺序逐轮调用 Adapter；用例之间使用 Semaphore 并发，避免对真实接口造成过载。
- **每条用例独立 session**：必须为每条用例生成唯一 `session_id`，避免上下文串台。
- **错误以数据形式归档**：Adapter 失败、超时、Runner 自身崩溃都必须以 `ConversationTrace.error` 字段返回，而不是让 `run_cases` 抛异常打断整个评测。
- **预设消息不触发调用**：`system` / `assistant` 预设 turn 仅入对话历史，禁止额外调用 Adapter（否则会污染对话上下文与计费）。
## Requirements

### 需求:Runner 必须为每条用例顺序执行所有 user turn

Runner MUST 遍历 `case.turns`，对 `role=user` 的 turn 把累积的 messages 通过 Adapter 调用一次，把返回的 assistant reply 追加到对话历史；对 `role=system` 或 `role=assistant` 的 turn 必须直接入历史，不触发 Adapter 调用。所有 turn 处理完毕后必须返回完整 `ConversationTrace`。

#### 场景:多轮用户输入

- **当** 一条用例的 turns 是 `[user, user]`（追问场景）
- **那么** Runner 必须调用 Adapter 两次，第二次调用时 messages 必须包含完整的"user1, assistant1, user2"历史

#### 场景:预设 system / assistant turn 不触发调用

- **当** 一条用例的 turns 起手是 `[system: "你是儿科医生"]`，然后是 `[user: "孩子发烧 39"]`
- **那么** Runner 必须只调用 Adapter 一次（针对 user turn），调用时 messages 第一条必须是预设的 system 消息

### 需求:Runner 必须为每条用例分配独立的 session_id

每条用例 MUST 生成形如 `medeval-<sample_id>-<random8>` 的 session_id，并贯穿该用例的全部轮次。不同用例之间必须使用不同 session_id；同一用例的不同轮次必须共享同一 session_id。

#### 场景:跨用例不串台

- **当** 评测一次性跑 100 条用例
- **那么** 至少存在 100 个不同的 session_id（用例之间不复用），并且每条用例的所有 turn 共用同一个 session_id

### 需求:Runner 必须支持每轮调用的超时与重试

Runner MUST 以 `timeout_s` 为单轮上限，超时必须以 `asyncio.TimeoutError` 触发重试（最多 `retry` 次）；Adapter 返回的 `ChatResponse.error` 非空时同样必须计入失败并重试；所有重试用完仍失败时，Runner 必须停止该用例后续 turn，并把最后一次错误写入 `ConversationTrace.error`。

#### 场景:首次超时但重试后成功

- **当** Adapter 第一次调用超过 `timeout_s`，第二次调用在时限内返回正常
- **那么** Runner 必须把第二次的回复写入对话历史，`trace.error` 必须为空，且该轮历史中没有"失败占位符"

#### 场景:全部重试用完仍失败

- **当** 设置 `retry=2`，三次调用都返回带 `error` 的响应
- **那么** Runner 必须停止该用例的后续轮次，`trace.error` 必须非空，且后续 user turn 的 messages 不再被发往 Adapter

#### 场景:超时不算第一轮成功

- **当** 一条多轮用例中第二轮全部重试都超时
- **那么** Runner 必须保留第一轮已成功的对话历史，但不会再追加第三轮的 user 输入到对话中

### 需求:Runner 必须以 Semaphore 控制并发度

Runner MUST 接受 `concurrency` 参数（默认 4），并使用 `asyncio.Semaphore` 限制同时在飞的用例数。对真实付费 API 必须能调低并发避免限流；对 mock 必须能调高加速。

#### 场景:并发度为 1 时严格串行

- **当** `concurrency=1`，输入 5 条用例
- **那么** 任意时刻最多只有 1 条用例的 Adapter 调用在执行（可用日志或调用时序验证）

#### 场景:返回的 trace 顺序必须与输入用例顺序一致

- **当** 并发执行 5 条用例
- **那么** `run_cases` 返回的 traces 列表必须与输入 cases 列表一一对应（位置不变），即便用例之间完成顺序不同

### 需求:Runner 必须在自身崩溃时也产出可消费的 Trace

为了防止某条用例的边界 bug 拖垮整轮评测，Runner MUST 对单条用例的执行加 try/except 包裹。Runner 自身的异常必须被捕获，对应 trace 必须以空 messages + `error="runner crashed: ..."` 形式返回，整体评测必须继续完成。

#### 场景:单条用例触发未预期异常

- **当** 某条用例由于 Adapter 内部 bug 抛出非 `error` 字段能承载的异常
- **那么** Runner 必须在该用例的 trace 中写入 `runner crashed: ...` 错误，其他用例必须不受影响地继续执行完毕

### 需求:Runner 必须记录每条用例的总耗时

`ConversationTrace.duration_ms` MUST 等于"从首轮 turn 开始到最后一轮 turn 结束"的实际墙钟耗时（毫秒，整数）。该字段用于报告中分析延迟。

#### 场景:duration_ms 单调非负

- **当** 任意一条用例执行完成（无论成功或失败）
- **那么** `trace.duration_ms` 必须为非负整数，且至少为 1（即便是即时返回也不能为 0 误报）

### 需求:Runner 必须支持进度回调

Runner MUST 接受 `on_progress` 可选回调，每完成一条用例时以 `(case, trace)` 形式调用一次。N-runs 模式下回调粒度细化为"完成一次 (case, run)"，回调签名兼容 `(case, trace)` 与 `(case, trace, run_idx)`。回调必须在 Semaphore 释放之前调用，以便 CLI 用 rich Progress 实时刷新计数。

#### 场景:进度回调被准确触发

- **当** 输入 N 条用例，传入 `on_progress=cb`
- **那么** 评测结束时 `cb` 必须被调用恰好 N × repeat 次，且每次的 case 必须对应一个 sample_id

### 需求:Runner 必须支持 N-runs 重复执行

`run_cases` MUST 接受 `repeat: int` 参数（默认 `1`，即与旧版完全一致）。当 `repeat=N>1` 时，对每条 case Runner MUST 顺序调用 adapter N 次，得到 N 个独立的 `ConversationTrace`，按调用顺序写入 `list[ConversationTrace]`。Runner 不得在同一条 case 内部并行 N 次调用（避免触发 adapter rate-limit），但跨 case 仍按 `concurrency` 参数并发。

每次重复 MUST 是完全独立的 adapter 会话——`ChatRequest.session_id` 必须不同（推荐拼接 `f"{base_session_id}#run{i}"`），让 adapter 能区分 retry vs 重复采样。

返回类型 MUST 统一为 `list[list[ConversationTrace]]`：外层 = case，内层长度 = `repeat`；`repeat=1` 时内层长度 1 以保持类型一致。

#### 场景:repeat=1 时与旧版语义等价

- **当** 用户跑 `run_cases(cases, adapter, repeat=1)` 或省略 `repeat` 参数
- **那么** Runner 行为必须与本 change 之前完全等价（每条 case 跑一次、不引入 N 维度判分）；返回结构外层顺序与 cases 一致、内层长度恒等于 1

#### 场景:repeat=3 时每条 case 跑三次

- **当** 用户跑 `run_cases(cases=[c1, c2], adapter, repeat=3)`
- **那么** adapter.chat MUST 被调用 6 次（c1×3 + c2×3，按 case 串内串行）；返回结构外层 len=2、内层 len=3，外层顺序与 cases 一致、内层顺序为重复序号 0/1/2

#### 场景:同 case 的 N 次调用 session_id 必须可区分

- **当** repeat=3，case 的基础 session_id 是 `s_001`
- **那么** 第 0/1/2 次调用 adapter 时 `ChatRequest.session_id` 必须分别是 `s_001#run0` / `s_001#run1` / `s_001#run2`（或等价的可区分约定）；adapter 必须能按 session_id 区分这是三次独立采样而非同一会话的延续

#### 场景:N 次中任一次失败必须保留所有完成的 trace

- **当** repeat=3，第 1 次 adapter 调用 timeout 失败
- **那么** Runner 必须保留 0/1/2 三次的 trace（失败那次 trace.error 非空）；下游聚合器必须基于"成功的 trace 子集"做 majority 折叠；若 N 次全部失败，最终聚合 case 必须标 `stable_fail` 并保留所有 error

### Requirement: Runner 必须采集每轮与整段会话耗时

runner 在每次调用 adapter 取得 bot 回复时 MUST 用单调时钟（`time.perf_counter`）测量该轮端到端耗时，并 MUST 将逐轮耗时写入 `ConversationTrace.turn_latencies_ms`；整段会话总耗时 MUST 复用既有的 `ConversationTrace.duration_ms`（已由 runner 填充）。新增字段 MUST 带默认值（空列表），且 MUST NOT 参与任何判分或 `gate_passed` 计算。

#### Scenario: 多轮会话记录逐轮与总耗时

- **WHEN** 一条三轮用例被执行
- **THEN** `ConversationTrace.turn_latencies_ms` MUST 含 3 个非负逐轮耗时，`duration_ms` MUST 为非负总耗时

#### Scenario: 延迟字段不影响判分

- **WHEN** 同一条 trace 在引入延迟采集前后分别判分
- **THEN** `gate_passed` 与各 judge verdict MUST 完全一致

### Requirement: N-runs 下必须逐次记录会话总耗时且错误 run 不计入聚合

在 N-runs 模式下，`CaseResult` MUST 以 `per_run_latency_ms` 逐次记录每次会话总耗时（N=1 时长度为 1）。`RunReport` MUST 聚合延迟统计（至少 平均、中位、P90、最大，单位 ms）。`trace.error` 非空的 run MUST NOT 计入 `RunReport` 的延迟聚合（避免超时把统计带偏）。

#### Scenario: N=3 逐次记录

- **WHEN** 一条用例 repeat=3 且三次均成功
- **THEN** `per_run_latency_ms` 长度 MUST 为 3，`RunReport.latency_summary` MUST 含 avg/median/p90/max

#### Scenario: 错误 run 不计入聚合

- **WHEN** 某次 run 因 adapter 三次重试失败导致 `trace.error` 非空
- **THEN** 该次耗时 MUST NOT 进入 `RunReport` 的延迟聚合统计

### Requirement: Runner 重试必须支持可配置指数退避并复用单一退避实现

Runner 对被测 chatbot 的调用重试 MUST 支持可配置的指数退避，且退避数学 MUST 与 LLM 后端（`judges/llm_backend.py`）复用同一实现（`medeval/retry.py` 的 `backoff_delay`），禁止两处各写一套退避公式。

退避默认 MUST 关闭（`retry_backoff_base_s=0.0`）以保持既有"立即重试"行为不变；仅当显式配置正的退避基数时，Runner 才在重试之间插入退避。被测 bot 调用的端到端超时 MUST 由 Runner 单一权威施加（`asyncio.wait_for`），适配器底层客户端超时仅作安全网。

#### Scenario: 默认配置行为不变

- **当** `retry_backoff_base_s` 取默认 `0.0` 且某轮调用失败需重试
- **那么** Runner MUST 不插入任何 sleep，重试时序与改造前逐位一致

#### Scenario: 启用退避后按指数等待

- **当** 配置 `retry_backoff_base_s > 0` 且某轮调用连续失败
- **那么** 第 N 次重试前 MUST 等待 `backoff_delay(N, base=retry_backoff_base_s, ...)` 秒，并受 `retry_backoff_max_s` 封顶

#### Scenario: 退避数学单一真值源

- **当** LLM 后端与 Runner 都需要指数退避
- **那么** 二者 MUST 调用同一 `backoff_delay` 实现，禁止复制各自的退避公式

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

### Requirement: N-runs 会话留痕落盘为可复现产物

dialog-runner MUST 能把每条用例的全部 N-runs `ConversationTrace` 落盘为可复现产物 `outputs/<run>/traces.jsonl.gz`（gzip + jsonl），并 MUST 在 run 阶段**增量写入**（每完成一个 `(sample_id, run_idx)` 即追加），使 run 阶段中途崩溃时已完成的留痕不丢失。落盘 MUST 受 `run.persist_traces` 开关控制，且当 `evaluate()` 未被告知输出目录时 MUST NOT 落盘（保持现状行为）。

落盘记录 MUST 按 `run.store_raw` 对 `raw_responses` 瘦身：`never` MUST 清空所有 `raw_responses`；`on_error` MUST 仅在该留痕 `error` 非空时保留 `raw_responses`、成功留痕清空；`always` MUST 原样保留。瘦身 MUST 不改动 `messages`/`turn_latencies_ms`/`error` 等离线重判所需字段。

#### Scenario: 默认开启增量落盘

- **WHEN** `medeval run` 使用默认配置（`persist_traces=true`、`store_raw=on_error`）完成一次评测
- **THEN** `outputs/<run>/traces.jsonl.gz` MUST 存在且可解析回每条用例的 N-runs 留痕，成功轮次的 `raw_responses` MUST 为空、报错轮次 MUST 保留

#### Scenario: 未告知输出目录时不落盘

- **WHEN** `evaluate()` 在未传入输出目录的场景（平台 / SDK / 测试）执行
- **THEN** MUST NOT 写任何 trace 产物，且判分产物与进度 phase MUST 与本次变更前逐字段一致

### Requirement: 基于已落盘成功留痕的断点续跑

dialog-runner MUST 支持断点续跑：给定上一次 run 的落盘留痕，执行 MUST 复用其中 `error` 为空的 `(sample_id, run_idx)` 留痕、SHALL NOT 对其重复调用 adapter，仅对缺失或失败的 `(sample_id, run_idx)` 重新执行。续跑 MUST 校验 adapter 指纹：当前配置的 adapter 指纹与落盘 meta 不一致时 MUST 拒绝复用并报清晰错误，MUST NOT 把不同 bot 的旧留痕混入本次结果。断点续跑 MUST 仅对 `local` 执行后端生效；当 `run.executor=ray` 且请求续跑时 MUST 抛清晰错误而非静默忽略。

#### Scenario: 复用成功留痕、重跑失败留痕

- **WHEN** 以 `--resume <prev_dir>` 续跑，且 prev 中部分用例成功、部分 `error` 非空
- **THEN** 成功的 `(sample_id, run_idx)` MUST 直接复用（不调 adapter），失败/缺失者 MUST 重新执行，最终产物结构与正常 run 一致

#### Scenario: adapter 指纹不一致拒绝续跑

- **WHEN** 续跑目标的 adapter 指纹与当前配置不一致
- **THEN** 系统 MUST 报错终止，MUST NOT 复用旧留痕

### Requirement: Runner 必须当场采集每轮 token 用量并写入 trace

runner 在每次调用 adapter 取得 bot 回复时 MUST 立即从 `ChatResponse.raw` 归一化抽取 token 用量，并 MUST 将逐轮用量写入 `ConversationTrace.turn_token_usage`。该采集 MUST 在任何 `raw_responses` 裁剪（`store_raw`）之前完成，使得即便成功轮次的 raw 被裁剪，token 用量仍保留。新增字段 MUST 带默认值（空列表）以兼容历史 `report.json`，且 MUST NOT 参与任何判分、`gate_passed` 或 `release_passed` 计算。归一化器认不出 usage 形状时 MUST 安全降级（记空占位），MUST NOT 抛错中断评测。

#### Scenario: 成功轮次采集 token 用量

- **WHEN** 一条用例的某 user 轮成功取得回复且后端返回 usage
- **THEN** `ConversationTrace.turn_token_usage` 对应位置 MUST 含 `prompt_tokens / completion_tokens / total_tokens`

#### Scenario: store_raw 裁剪后 token 仍在

- **WHEN** `store_raw=on_error` 且该轮成功（raw 被裁剪）
- **THEN** `turn_token_usage` MUST 仍保留该轮 token 用量

#### Scenario: token 字段不影响判分

- **WHEN** 同一条 trace 在引入 token 采集前后分别判分
- **THEN** `gate_passed`、`release_passed` 与各 judge verdict MUST 完全一致

### Requirement: N-runs 下必须逐次记录会话总 token 且错误 run 不计入聚合

在 N-runs 模式下，`CaseResult` MUST 以 `per_run_tokens` 逐次记录每次会话的总 token（N=1 时长度为 1，由 `turn_token_usage` 求和得到）。`RunReport` MUST 聚合 token 统计（至少总 token 与平均每 run token）。`trace.error` 非空的 run MUST NOT 计入 `RunReport` 的 token 聚合，与延迟聚合同口径。

#### Scenario: N=3 逐次记录

- **WHEN** 一条用例 repeat=3 且三次均成功并返回 usage
- **THEN** `per_run_tokens` 长度 MUST 为 3，`RunReport.token_summary` MUST 含总 token 与平均每 run token

#### Scenario: 错误 run 不计入聚合

- **WHEN** 某次 run 因 adapter 重试失败导致 `trace.error` 非空
- **THEN** 该次 token MUST NOT 进入 `RunReport.token_summary`

