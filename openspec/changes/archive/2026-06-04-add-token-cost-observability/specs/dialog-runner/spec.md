## ADDED Requirements

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
