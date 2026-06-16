## MODIFIED Requirements

### Requirement: scoring_point verdict 为软分且不阻塞 gate_passed

`scoring_point.*` verdict MUST NOT 参与 `hard_gate_passed` 与 `gate_passed` 的计算。Aggregator MUST 将其纳入 `soft_score`/`soft_score_max` 的统计。报告层 MUST 将 `scoring_point.summary` 净分按 `scoring_point_function_cap`（默认 0.15）映射进功能模块综合分；该映射 MUST NOT 改变 gate 轴，仅影响 `release_passed` 所依据的四模块分。

#### Scenario: 得分点低分不拉挂 gate 但拉低功能分

- **WHEN** 一条用例 HardGate 与 Rule 全过，但 `scoring_point.summary` 归一化得分仅 0.2（`achieved=1, max_positive=5`）
- **THEN** `gate_passed` MUST 仍为 True，功能模块分 MUST 低于无得分点时的满分

#### Scenario: 历史用例软分语义不变

- **WHEN** 评测一批无 `scoring_points` 的历史用例
- **THEN** `soft_score`/`gate_passed` MUST 与引入本判官前完全一致
