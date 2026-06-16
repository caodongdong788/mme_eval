## MODIFIED Requirements

### Requirement: scoring_point verdict 为软分且不阻塞 gate_passed

`scoring_point.*` verdict MUST NOT 参与 `hard_gate_passed` 与 `gate_passed` 的计算。Aggregator MUST 将其纳入 `soft_score`/`soft_score_max` 的统计。报告层 MUST 按指南总扣分映射功能模块：`miss_pts = Σ(未命中正分点 points) + Σ(命中负分点 |points|)`，`function -= miss_pts × 0.1`（k 固定 0.1）；MUST NOT 因命中正分点而增加功能分。该映射 MUST NOT 改变 gate 轴，仅影响 `release_passed` 所依据的四模块分；功能模块允许为负。

#### Scenario: 正分漏 3 分扣功能 0.3

- **WHEN** 用例有正分 scoring_point 共 6 分，其中 3 分权重未命中
- **THEN** 功能模块 MUST 额外扣除 0.3

#### Scenario: 命中正分点不加分

- **WHEN** 全部正分 scoring_point 命中且无负分踩雷
- **THEN** 功能模块 MUST NOT 因 scoring_point 增加分数
