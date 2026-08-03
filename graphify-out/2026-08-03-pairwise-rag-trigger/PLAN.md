# Pairwise 真实 RAG 触发筛选实施计划

## 目标

Pairwise 新增 `rag_triggered_only` 范围。系统根据两侧 Run 的 `enable_rag` 自动识别 A 或 B 中的 RAG 组，只把该侧真实调用过医学文献 RAG 的同题回答送入 Pairwise Judge，避免“仅开放工具但未调用”的 Case 稀释结论。A/B 的基线与本次语义保持不变，不因 RAG 侧位置而交换。

## 单一判定信号

- 使用 `case_result.rag_status`，该字段来自同步后的 Agent/Langfuse 工具链。
- `hit`、`miss`、`failed`、`triggered` 代表真实发生过 RAG 工具调用。
- `not_triggered` 与 `unknown` 不进入 `rag_triggered_only`。
- 不用 Run 的 `adapter_overrides.enable_rag` 代替真实调用信号；开关只作为 A/B 被测差异展示。

## 数据流

1. Pairwise 预检根据 `enable_rag` 自动识别 RAG 侧，再读取 A/B 同题的 `rag_status`，返回可入选数、未触发数、未知数和两侧状态分布。
2. 发起对比时保存 `scope=rag_triggered_only`。
3. 后台任务取共有 Sample ID，仅保留自动识别出的 RAG 侧状态属于真实调用集合的 Case。
4. 汇总保存本次 RAG 筛选统计；人工校准重算时保留该统计。
5. Pairwise 详情接口按 Sample ID 附加 A/B 的真实 RAG 状态，逐用例表可审计。
6. 前端发起区展示“仅 B 实际触发 RAG”选项及预检数量，详情页展示筛选摘要和 A/B 状态。

## 验收标准

- RAG 侧=`hit/miss/failed/triggered` 的 Case 会被比较，RAG 侧=`not_triggered/unknown` 的 Case 不会调用 Pairwise Judge；A/B 任一侧均可作为 RAG 侧。
- “全部用例”和“仅差异用例”行为不变。
- 预检和完成后的汇总能解释共有题、入选题、排除题及未知题数量。
- 详情列表逐题显示 A/B 真实 RAG 状态。
- 后端 Pairwise 测试与前端生产构建通过。

## 验证结果

- Pairwise/RAG 针对性测试：20 passed（覆盖 A/B 任一侧为 RAG 组）。
- 完整后端回归：433 passed，1 skipped。
- 前端 `npm run build`：通过。
- 本地 Docker：应用与 PostgreSQL 均 healthy；OpenAPI 已暴露 `rag_triggered_only`、`rag_analysis`、`rag_status_a/b`。
