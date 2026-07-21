# Reporting

## Purpose

定义指南扣分、三端 45 分制、医学安全归零、评级和报告追溯口径。JSON、Markdown、Excel 与平台持久化必须使用同一计算结果，不保留旧四模块含义。

## Requirements

### Requirement: 指南缺分必须从绑定维度扣除

Reporter MUST 对每条指南计算 `missing=max_score-score`，并以 `final_dimension=max(0, raw_dimension-missing)` 扣分。多条指南 MUST 依次累积扣分，维度不得低于 0。

#### Scenario: 原始 4 分且指南得 2/3

- **WHEN** 指南绑定该维度且缺 1 分
- **THEN** 最终维度分 MUST 为 3

### Requirement: 三端总分必须为 45 分制

医生端 MUST 为三个医生维度之和（满分15）；护士端 MUST 将两个护士维度 `/10` 归一为 `/15`；患者端 MUST 为三个患者维度之和（满分15）。三端总分 MUST 满分45。

#### Scenario: 护士两个维度满分

- **WHEN** 个性化和方案可行性均为 5
- **THEN** 护士端 MUST 为 15

### Requirement: 医学安全性失败必须归零

当医学安全性不是 5 时，Reporter MUST 将该维度视为 0，并 MUST 将整题总分设为 0。

#### Scenario: 其它七维满分但医学安全性为 0

- **WHEN** `medical_safety=0`
- **THEN** 总分 MUST 为 0 且 `release_passed` MUST 为 false

### Requirement: 评级和通过结论必须固定

总分 `≥40.5` MUST 为优秀、`≥36` MUST 为良好、`≥27` MUST 为合格，其余 MUST 为不合格。合格及以上且 trace 无错误时 `release_passed` MUST 为 true。

#### Scenario: 总分 27

- **WHEN** 无执行错误且总分恰为 27
- **THEN** grade MUST 为合格且 `release_passed` MUST 为 true

### Requirement: 产物必须可追溯

JSON、Markdown 与 Excel MUST 展示八维原始分、指南逐项得分、指南扣分后的八维分、三端分、45 分总分、评级与扣分理由。延迟、token 和 trace URL MUST 仅作观测，不得参与评分。

#### Scenario: 指南未满分

- **WHEN** 一条指南有缺分
- **THEN** 报告 MUST 展示该指南得分/满分、理由、证据和对应维度扣分
