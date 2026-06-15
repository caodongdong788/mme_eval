## 1. 模型字段

- [x] 1.1 在 `ConversationTrace` 复用既有 `duration_ms` 作为整段会话总耗时，新增逐轮耗时 `turn_latencies_ms: list[float] = Field(default_factory=list)`
- [x] 1.2 在 `CaseResult` 增 `per_run_latency_ms: list[float] = Field(default_factory=list)`
- [x] 1.3 在 `RunReport` 增 `latency_summary: dict = Field(default_factory=dict)`（avg/median/p90/max，单位 ms）

## 2. Runner 计时

- [x] 2.1 在 `medeval/runner/executor.py` 每次 adapter 调用外层用 `time.perf_counter()` 计时，写入逐轮耗时
- [x] 2.2 整段会话总耗时复用既有 `duration_ms`（runner 已填充）
- [x] 2.3 N-runs 下把每次会话总耗时收集进 `CaseResult.per_run_latency_ms`（在 `fold_n_runs` 折叠）

## 3. 聚合与报告

- [x] 3.1 聚合 `RunReport.latency_summary`，统计时过滤 `trace.error` 非空的 run
- [x] 3.2 在 markdown 报告新增"性能（仅记录）"段，展示 avg/median/p90/max 并标注"仅记录、不计分、不否决"
- [x] 3.3 无可用延迟数据时该段显示 N/A，不渲染空表

## 4. 测试

- [x] 4.1 单测：延迟字段不影响 `overall_passed` 与各 verdict（判分零耦合）
- [x] 4.2 单测：N=3 时 `per_run_latency_ms` 长度为 3，`latency_summary` 含 avg/median/p90/max
- [x] 4.3 单测：错误 run 不计入延迟聚合
- [x] 4.4 单测：历史无延迟字段的 report.json 仍可反序列化（默认值兼容）
