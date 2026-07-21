# 报告增量规格

## MODIFIED Requirements

### Requirement: 系统必须按三端 45 分制计算结论

Reporter MUST 先将指南缺分从绑定维度原始分扣除并将维度分下限限制为 0；随后 MUST 计算医生端 `/15`、护士端原始 `/10` 后归一 `/15`、患者端 `/15`，总分满分 45。医学安全性为 0 时总分 MUST 为 0。

#### Scenario: 护士端满分归一

- **WHEN** 个性化与方案可行性均为 5
- **THEN** 护士端 MUST 记 15 分而不是 10 分

### Requirement: 报告必须输出四档结论与可追溯指南扣分

总分 `≥40.5` MUST 为优秀、`≥36` MUST 为良好、`≥27` MUST 为合格、其余 MUST 为不合格；合格及以上 MUST 令 `release_passed=true`，执行错误除外。报告 MUST 展示 8 维原始分、每条指南得分/满分、8 维最终分、三端分与逐条指南扣分理由，且 MUST NOT 使用旧四模块或 0～1 分制标签。

#### Scenario: 指南满分不扣分

- **WHEN** 指南模型得分等于 `max_score`
- **THEN** 绑定维度 MUST 不因该指南扣分，扣分原因 MUST 不生成虚假失分项

