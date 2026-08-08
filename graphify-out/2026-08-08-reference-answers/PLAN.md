# Reference Answers 结构兼容与展示计划

## 目标

- 兼容导入包中的 Case 2.1 结构：八维与指南均可使用 `criteria`、`reference_answers` 和独立 `deduction_rule`。
- 保持旧版 2.0 YAML 的 `dimension_criteria: [..]` 与 `criterion` 写法可继续导入。
- 在 Benchmark 结构化编辑器和评测用例明细中清晰展示、编辑“好答案”。

## 实施

1. 为八维要求与指南新增严格的好答案字段模型，并将旧字段归一到同一运行期结构。
2. 更新八维和指南 Judge 的上下文，让好答案作为非逐字要求的质量参考。
3. 在 Benchmark 的“八维评测要求”和“指南扣分点”中展示、维护好答案。
4. 在评测用例明细新增只读“好答案参考”面板，读取运行时冻结的 Case 数据。
5. 补充 2.1 ZIP 导入、旧版兼容、Judge 上下文和前端展示测试，并更新 Case YAML 文档。

## 验收

- 用户提供的 ZIP 可通过用例校验并保留有值的 `reference_answers`。
- 保存和重新读取 Benchmark 后，好答案不会丢失。
- 评测用例明细可按维度/指南查看好答案。
- 相关 Python 测试与前端生产构建通过。

## 完成情况

- 已兼容 2.1 的对象式八维/指南结构，并兼容旧 2.0 的列表式 `dimension_criteria` 与 `criterion`。
- `reference_answers: null` 会安全归一为空列表；非空好答案会在 Benchmark 编辑器、运行时 Case 快照、评测详情和 Judge 参考上下文中保留。
- 已用用户提供的 ZIP 实测加载 63 条 Case，识别并保留 400 条非空好答案。
- 校验通过：`446 passed, 3 skipped`、前端 `94 passed`、`npm run build`、`import server.app`。
