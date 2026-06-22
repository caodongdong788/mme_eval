## ADDED Requirements

### Requirement: 套件必须包含记忆召回专集覆盖五种单 session 题型

乳腺癌 benchmark MUST 在 `cases/breast_cancer/memory.yaml` 提供 **15** 条记忆召回用例。全部用例 `scenario` MUST 为 `记忆召回`；`sub_scenario` MUST 以五种题型前缀之一开头：`隐式综合`、`显式召回`、`干扰召回`、`信息更正`、`抗假记忆`，后接 `·` 与临床主题描述。每条 MUST 含 `rubric.multi_turn_consistency` 且 `scoring_points` 不少于 3 条；`sample_id` MUST 以 `bc_mem_` 前缀保证唯一。

#### Scenario: 五种题型均有覆盖

- **WHEN** 加载 `cases/breast_cancer/memory.yaml`
- **THEN** 五种 `sub_scenario` 题型前缀 MUST 各至少出现 2 次，合计 MUST 为 15 条用例

#### Scenario: 记忆题结构合规

- **WHEN** 任一条 `bc_mem_*` 用例被加载
- **THEN** 该用例 MUST 含至少 3 个 user turn、`multi_turn_consistency` rubric、以及正负 `scoring_points` 以支持部分召回计分
