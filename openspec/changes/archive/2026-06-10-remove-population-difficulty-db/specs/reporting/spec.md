## MODIFIED Requirements

### 需求:系统必须把 CaseResult 列表聚合为多维切片 RunReport

`build_report` MUST 返回 `RunReport`，至少包含 `total`、`passed`、`hard_gate_failed`、`by_level`、`by_scenario`、`failure_tag_counter` 字段。每个切片字典 MUST 以 `{total, passed, hard_failed}` 三键存储计数，便于后续直接计算通过率。MUST NOT 再聚合 `by_population` 或 `by_difficulty`。

#### Scenario: 按 level 聚合

- **WHEN** 输入 30 条 CaseResult，其中 L1 / L2 / L3 / L4 各若干
- **THEN** `report.by_level["L3"]["total"]` MUST 等于 L3 用例总数；`passed` MUST 等于 L3 中 `release_passed=True` 的数量；`hard_failed` MUST 等于 L3 中 `hard_gate_passed=False` 的数量

#### Scenario: failure_tag_counter 按频次降序

- **WHEN** 失败标签 `missed_red_flag` 出现 5 次、`improper_prescription` 出现 3 次
- **THEN** `failure_tag_counter` 字段 MUST 以 `missed_red_flag` 在前的顺序排列（dict 插入顺序即频次降序）
