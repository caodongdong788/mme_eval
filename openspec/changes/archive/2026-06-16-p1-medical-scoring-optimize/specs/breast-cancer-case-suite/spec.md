## MODIFIED Requirements

### Requirement: 套件必须包含乳腺癌专属红旗急症并走 hard_gate

内置 benchmark 肿瘤急症红旗题（``bc_rf_*``）MUST ≥11 条（P1 扩库后）。红旗题 MUST NOT 再声明 `triage_quality` rubric（分诊由 HardGate 独占）。

#### Scenario:红旗题数量达标

- **WHEN** 加载 `config.yaml` 指向的 breast_cancer 套件
- **THEN** `bc_rf_*` 用例数 MUST ≥ 11

## ADDED Requirements

### Requirement: 乳腺癌 benchmark 必须含人群特异专题

系统 MUST 在 `cases/breast_cancer/population.yaml` 提供 8 道 `score_profile=population` 用例，评测人群盲区与专科边界。

#### Scenario:population 专题存在

- **WHEN** 扫描 `cases/breast_cancer/population.yaml`
- **THEN** MUST 加载 8 条 `score_profile=population` 用例
