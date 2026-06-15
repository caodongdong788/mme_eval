## Context

runner（`medeval/runner/executor.py`）以异步并发逐轮调用 adapter 取得 bot 回复，组装成 `ConversationTrace`，再交判分。目前不记录任何耗时。N-runs 模式下每条 case 会跑 N 次 trace。本设计只在执行链路上加"计时与落盘"，不触碰判分与评分。

## Goals / Non-Goals

**Goals:**
- 记录每轮 adapter 调用耗时与每段会话总耗时。
- 在 N-runs 下逐次记录会话总耗时，报告聚合 平均/中位/P90。
- 报告清晰呈现延迟，并标注"仅记录、不计分、不否决"。
- 完全向后兼容：新增字段默认值，判分零影响。

**Non-Goals:**
- 不做并发/吞吐/可用率压测（需独立压测框架，超出本期）。
- 不把延迟纳入综合分或评级（属后续；本期明确不计分）。
- 不对延迟设阈值或否决。

## Decisions

### 决策 1：计时粒度——每轮 + 整会话
在 runner 每次 adapter 调用外层用 `time.perf_counter()` 计时，得到该轮 `elapsed_ms`；一段会话所有轮次之和（或首尾差）记为 `total_latency_ms`。
- 记录"每轮"便于定位"哪一轮慢"；记录"整会话"作为对外主指标。
- **备选**：只记整会话。否决——丢失多轮中单轮定位能力，成本几乎一样。

### 决策 2：字段落点
- `ConversationTrace`：增 `total_latency_ms: float = 0.0`；每轮耗时挂在对应 assistant 消息或单独的 `turn_latencies_ms: list[float] = []`。
- `CaseResult`：增 `per_run_latency_ms: list[float] = Field(default_factory=list)`（N-runs 下每次会话总耗时；N=1 时长度为 1）。
- `RunReport`：增聚合 `latency_summary: dict`（avg/median/p90/max，单位 ms），默认空 dict。

### 决策 3：错误 run 不计入
`trace.error` 非空（adapter 三次重试都失败）的 run MUST NOT 计入延迟聚合——否则超时会把统计带偏。该 run 的耗时仍可记录在 `per_run_latency_ms`（便于排查），但聚合时过滤。

### 决策 4：纯展示，判分零耦合
延迟字段不进任何 judge、不进 `overall_passed`、不进 fingerprint。报告以独立"性能（仅记录）"段呈现，与通过率/软分分区。

## Risks / Trade-offs

- [把网络/限流抖动当成 bot 性能] → 报告标注"含网络与排队耗时，非纯模型推理时延"；错误 run 不计入。
- [并发下计时受调度影响] → 记录 wall-clock 端到端耗时即可满足"先有数据"目标；精细化压测留待后续独立 change。
- [被误读为性能合格线] → 报告明确"仅记录、不计分、不否决"。

## Open Questions

- 后续是否将延迟纳入综合分的"性能维度"权重 → 留待 `add-weighted-scoring-and-grading` 及之后（本期明确不计分）。
