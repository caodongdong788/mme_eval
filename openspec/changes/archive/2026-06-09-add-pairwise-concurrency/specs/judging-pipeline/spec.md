# judging-pipeline (delta)

## ADDED Requirements

### Requirement: Pairwise 并发执行

Pairwise 对比 MUST 支持两层并发以加速，且 MUST NOT 改变任何判定语义（winner/confidence/
dimension_winners 与串行实现一致）：

- **题内并行**：当 `swap_debias=true` 时，`PairwiseComparator.compare_case` MUST 用
  `asyncio.gather` 并行执行顺序①与顺序②两次裁判调用；位置消偏与医疗保守覆盖语义 MUST 不变。
- **题间并发**：`run_pairwise_comparison` MUST 以可配置并发度 N（`Semaphore(N)`）并发执行多道
  题的 `compare_case`，N 取自所用判分模型的 `pairwise_concurrency`（默认 4）。
- **安全落库**：并发下写 `PairwiseCaseVerdict` 与递增 `done_cases` 的临界区 MUST 串行化
  （`asyncio.Lock`），保证不丢 verdict、`done_cases` 单调递增、最终 `summary` 与串行口径一致。

并发是执行方式，MUST NOT 纳入 `PairwiseComparator.fingerprint()`（不影响判分语义）。

#### Scenario: 题内两次裁判并行

- **WHEN** `swap_debias=true` 的 `compare_case` 执行
- **THEN** 顺序①与顺序②两次裁判调用 MUST 并发调度，最终 `winner`/`confidence`/
  `dimension_winners` 与串行执行完全一致

#### Scenario: 题间并发不影响汇总口径

- **WHEN** 一次对比以 `pairwise_concurrency=4` 并发跑完全部用例
- **THEN** verdict 总数、`done_cases` 终值与逐项 `summary`（胜/平/负、低置信、维度胜率）MUST
  与串行执行口径一致

### Requirement: 判分模型携带 Pairwise 并发度

`JudgeModelConfig` MUST 携带 `pairwise_concurrency: int`（默认 4，取值 MUST ≥ 1），表示该判分
模型用于 Pairwise 对比时的题间并发度。该字段 MUST 仅作用于 Pairwise 对比，MUST NOT 影响主评测
链路（`service.py` 的被测 bot 调用并发与 judge 并发仍由 `config.run.concurrency` 决定）。

读取类接口 MUST 暴露 `pairwise_concurrency`；创建/更新接口 MUST 接受该字段并校验 ≥ 1。

#### Scenario: 新建判分模型默认并发为 4

- **WHEN** 创建判分模型时未提供 `pairwise_concurrency`
- **THEN** 该模型的 `pairwise_concurrency` MUST 为 4

#### Scenario: 并发度仅作用于对比

- **WHEN** 某判分模型的 `pairwise_concurrency` 被改为 8 后发起一次主评测
- **THEN** 主评测的并发行为 MUST 不受影响（仍由 `config.run.concurrency` 决定）
