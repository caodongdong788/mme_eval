## MODIFIED Requirements

### Requirement: ScoringPointJudge 必须有稳定 fingerprint 且 N-runs 下只调用一次

`ScoringPointJudge.fingerprint()` MUST 覆盖其 prompt 模板、provider、model、temperature；MUST NOT 覆盖 case 的得分点内容（得分点属用例数据，不纳入 fingerprint）。在 N-runs 模式下，`ScoringPointJudge` 作为 LLM 判官 MUST 只对代表性 trace 调用一次（与 `LLMJudge` 一致以控成本），其 fingerprint MUST 经 verdict 进入 `RunReport.judge_fingerprints`。

#### Scenario: 改 prompt/model 改变 fingerprint

- **WHEN** 修改 `ScoringPointJudge` 的 prompt 模板或 model
- **THEN** `fingerprint()` MUST 变化；仅修改得分点内容 MUST NOT 改变 fingerprint

#### Scenario: N=3 下得分点判官只调一次

- **WHEN** 一条带得分点的用例 repeat=3
- **THEN** `ScoringPointJudge` 调用次数 MUST 为 1（仅代表性 trace），HardGate/Rule MUST 各跑 3 次

### Requirement: 指南要点库必须以带版本锚点的 scoring_points 承载

判分流水线 MUST 以既有 `ScoringPoint`（`criterion` + `points` + `guideline`）与 `ScoringPointJudge` 作为「指南要点库」的载体：临床方案的「标准答案依据」MUST 被展开为 per-case 的机判 `scoring_points`，每条要点 MUST 是单一、可逐点判定的命题。引用具名权威指南（如 ASCO / NCCN / 中国抗癌协会 CACA）的 `guideline` 锚点 MUST 携带版本年份（如 "NCCN 2025版乳腺癌筛查指南"），使指南更新可经 `config_snapshot` 与判官 fingerprint 在 diff 中体现；非指南性锚点（如对抗题「合格标准」、三甲「流程示例」）MUST NOT 被强制要求版本。

#### Scenario: 标准答案依据展开为逐点要点

- **WHEN** 一道知识/治疗类用例迁移自带「标准答案依据」的题目
- **THEN** 其 `scoring_points` MUST 含 3–5 条可逐点判定的要点，关键临床结论 MUST 各自成点

#### Scenario: 具名指南锚点携带版本

- **WHEN** 某得分点 `guideline` 引用 ASCO / NCCN / CACA
- **THEN** 该锚点字符串 MUST 含版本年份
