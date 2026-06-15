## Why

对标方案把"性能与运维"列为一个评测维度，但我们当前完全不记录被测 chatbot 的响应耗时——无法回答"这个 bot 快不快""哪类用例慢"。本期先补上最基础、零风险的一环：**记录每次对话的耗时**，先有数据、进报告，但**不参与评分、不设否决**（性能是否计分留待后续）。

## What Changes

- 在 runner 执行每轮 adapter 调用时记录耗时，并在 `ConversationTrace` 上保留每轮耗时与整段会话总耗时。
- 在 `CaseResult` 记录该用例每次 run 的会话总耗时（N-runs 下为列表）。
- 在 `RunReport` 聚合延迟统计（平均、中位、P90）。
- 报告新增"性能（仅记录）"段展示延迟统计，并明确标注**不计分、不否决**。
- 不引入任何评分、阈值或否决逻辑；adapter 出错的 run 不污染延迟统计。

## Capabilities

### New Capabilities
<!-- 无新增 capability -->

### Modified Capabilities
- `dialog-runner`: 执行每轮对话时 MUST 采集耗时并写入 trace/result；N-runs 下逐次记录。
- `reporting`: 报告 MUST 呈现延迟统计且明确标注"仅记录、不计分"。

## Impact

- 代码：`medeval/models.py`（`ConversationTrace`/`CaseResult`/`RunReport` 增延迟字段）、`medeval/runner/executor.py`（计时）、`medeval/reporter/markdown_report.py`、`tests/`。
- 兼容性：所有新增字段带默认值（0 / 空列表），历史 `report.json` 与现有判分行为完全不变。
- 依赖：仅用标准库计时（`time.perf_counter`），无新增依赖。
