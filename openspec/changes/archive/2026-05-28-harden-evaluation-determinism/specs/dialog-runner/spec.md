## ADDED Requirements

### Requirement: Runner 必须支持 N-runs 重复执行

`run_cases` MUST 接受 `repeat: int` 参数（默认 `1`，即与旧版完全一致）。当 `repeat=N>1` 时，对每条 case Runner MUST 顺序调用 adapter N 次，得到 N 个独立的 `ConversationTrace`，按调用顺序写入 `list[ConversationTrace]`。Runner 不得在同一条 case 内部并行 N 次调用（避免触发 adapter rate-limit），但跨 case 仍按 `concurrency` 参数并发。

每次重复 MUST 是完全独立的 adapter 会话——`ChatRequest.session_id` 必须不同（推荐拼接 `f"{base_session_id}#run{i}"`），让 adapter 能区分 retry vs 重复采样。

#### 场景: repeat=1 时与旧版完全等价

- **WHEN** 用户跑 `run_cases(cases, adapter, repeat=1)` 或省略 `repeat` 参数
- **THEN** Runner 行为必须与本 change 之前完全一致：每条 case 跑一次、返回 `list[ConversationTrace]` 长度等于 case 数；不得新增任何 N 维度

#### 场景: repeat=3 时每条 case 跑三次

- **WHEN** 用户跑 `run_cases(cases=[c1, c2], adapter, repeat=3)`
- **THEN** adapter.chat MUST 被调用 6 次（c1×3 + c2×3，按 case 串内串行）；返回结构 MUST 是 `list[list[ConversationTrace]]`，外层 len=2、内层 len=3，外层顺序与 cases 一致、内层顺序为重复序号 0/1/2

#### 场景: 同 case 的 N 次调用 session_id 必须可区分

- **WHEN** repeat=3，case 的基础 session_id 是 `s_001`
- **THEN** 第 0/1/2 次调用 adapter 时 `ChatRequest.session_id` 必须分别是 `s_001#run0` / `s_001#run1` / `s_001#run2`（或等价的可区分约定）；adapter 必须能按 session_id 区分这是三次独立采样而非同一会话的延续

#### 场景: N 次中任一次失败必须保留所有完成的 trace

- **WHEN** repeat=3，第 1 次 adapter 调用 timeout 失败
- **THEN** Runner 必须保留 0/1/2 三次的 trace（失败那次 trace.error 非空）；下游聚合器必须基于"成功的 trace 子集"做 majority 折叠；若 N 次全部失败，最终聚合 case 必须标 `stable_fail` 并保留所有 error
