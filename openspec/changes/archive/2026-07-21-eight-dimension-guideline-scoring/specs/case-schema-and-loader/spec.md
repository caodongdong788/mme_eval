# 用例 Schema 与加载器增量规格

## MODIFIED Requirements

### Requirement: TestCase 必须只接受新版八维评测结构

正式 Case YAML MUST 声明 `schema_version: "2.0"` 与必填 `evaluation`。`evaluation.dimension_criteria` 的键 MUST 取自固定八维词表；`evaluation.guidelines` 的每项 MUST 含 Case 内唯一 `id`、目标 `dimension`、非空 `criterion`、非空 `source` 与 1～5 整数 `max_score`。系统 MUST NOT 保留旧 `score_profile`、`expected_behavior`、`hard_gates`、`rubric` 或 `scoring_points` 输入字段。

#### Scenario: 合法指南部分分配置

- **WHEN** Case 声明一条 `dimension=professional_accuracy`、`max_score=3` 的指南
- **THEN** loader MUST 成功构造该指南并保留其满分

#### Scenario: 指南不能绑定安全维

- **WHEN** 指南声明 `dimension=medical_safety`
- **THEN** loader MUST 拒绝该 Case，避免二值 Gate 被扣成中间分

#### Scenario: 旧 Case 被拒绝

- **WHEN** YAML 仍使用 `rubric` 或 `scoring_points` 且没有 v2 evaluation
- **THEN** loader MUST fail fast 且不进入 Runner
