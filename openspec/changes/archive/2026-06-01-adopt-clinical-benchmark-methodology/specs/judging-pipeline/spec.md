## ADDED Requirements

### Requirement: 指南要点库必须以带版本锚点的 scoring_points 承载

判分流水线 MUST 以既有 `ScoringPoint`（`criterion` + `points` + `guideline`）与 `ScoringPointJudge` 作为「指南要点库」的载体：临床方案的「标准答案依据」MUST 被展开为 per-case 的机判 `scoring_points`，每条要点 MUST 是单一、可逐点判定的命题。引用具名权威指南（如 ASCO / NCCN / 中国抗癌协会 CACA）的 `guideline` 锚点 MUST 携带版本年份（如 "NCCN 2025版乳腺癌筛查指南"），使指南更新可经 `case_version` 与 snapshot 在 diff 中体现；非指南性锚点（如对抗题「合格标准」、三甲「流程示例」）MUST NOT 被强制要求版本。

#### Scenario: 标准答案依据展开为逐点要点

- **WHEN** 一道知识/治疗类用例迁移自带「标准答案依据」的题目
- **THEN** 其 `scoring_points` MUST 含 3–5 条可逐点判定的要点，关键临床结论 MUST 各自成点

#### Scenario: 具名指南锚点携带版本

- **WHEN** 某得分点 `guideline` 引用 ASCO / NCCN / CACA
- **THEN** 该锚点字符串 MUST 含版本年份

### Requirement: 指南要点库必须经 ScoringPointJudge 派生指南匹配率

对声明了带 `guideline` 锚点 scoring_points 的用例，判分流水线 MUST 经 `ScoringPointJudge` 逐点判命中，并 MUST 在带锚点子集上派生指南匹配率（按点计数）。该指标 MUST 仅作度量与展示，本期 MUST NOT 参与任何否决或合格判定；无带锚点得分点的用例 MUST 记为 N/A 且不计入聚合分母。

#### Scenario: 迁移用例跑通指南匹配率

- **WHEN** 一道带版本指南锚点 scoring_points 的迁移用例经 `ScoringPointJudge` 判定全部命中
- **THEN** 其指南匹配率 MUST 为 1.0，且 MUST NOT 因此改变 `overall_passed`
