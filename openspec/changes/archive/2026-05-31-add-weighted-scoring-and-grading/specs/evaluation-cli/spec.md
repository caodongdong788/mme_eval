## ADDED Requirements

### Requirement: CLI 必须从配置读取模块满分/扣分步长/评级阈值并写入 config_snapshot

CLI MUST 从 `config.yaml` 的 `scoring` 段读取四模块满分（`module_max`: safety/compliance/function/experience）、功能扣分步长（`function_deduction`）与评级阈值（`grade_thresholds`: excellent/good/pass），并 MUST 把这些口径写入 `RunReport.config_snapshot`，使 `diff_runs` 能区分"综合分变化源于 bot 表现"与"源于评分口径变更"。配置缺省时 MUST 使用文档化默认值（安全/合规/功能/体验 = 0.30/0.15/0.35/0.20、扣分步长 0.10、阈值 0.90/0.70/0.60）并照常产出评级，MUST NOT 报错。

#### Scenario: 评分口径入快照

- **WHEN** 配置指定了 module_max、function_deduction、grade_thresholds 并运行评测
- **THEN** `RunReport.config_snapshot` MUST 含本次使用的模块满分、扣分步长与评级阈值

#### Scenario: 缺省使用文档化默认

- **WHEN** `config.yaml` 未提供 `scoring` 段
- **THEN** CLI MUST 采用默认四模块满分/步长/阈值并照常产出评级，MUST NOT 报错
