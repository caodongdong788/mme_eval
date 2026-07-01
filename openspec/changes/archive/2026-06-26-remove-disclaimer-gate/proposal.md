# Proposal: remove-disclaimer-gate

## Why

cx-agent 已在产品能力侧统一提供免责声明，评测平台继续逐 case 要求模型输出免责话术会重复惩罚，并把注意力从医疗安全红线（红旗分诊、处方/确诊边界）上稀释掉。

## What

- HardGateJudge 不再生成 `hard_gate.disclaimer` verdict。
- 新用例、新导入、新失败标签配置不再包含 `require_disclaimer` / `disclaimer_miss`。
- 历史报告中已有的 `hard_gate.disclaimer` verdict 仍按兼容逻辑忽略，不影响 `hard_gate_passed`、`compliance_failed` 或合规得分。
- 乳腺癌内置 case 删除免责相关字段与候选标签。

## Scope

- **In**: `medeval` 判分/标签词表、内置乳腺癌 cases、README/启发式治理文档、相关 tests。
- **Out**: cx-agent 产品侧免责声明能力、历史 report.json 数据迁移、前端 UI 新页面。

## Success

- 新评测结果不再出现 `hard_gate.disclaimer` verdict。
- 内置 `cases/breast_cancer` 不再含 `require_disclaimer` 或 `disclaimer_miss`。
- `/api/config/failure-tags` 不再暴露 `disclaimer_miss`。
- `medeval verify-heuristics`、相关 pytest、`medeval run --config config.yaml --dry-run` 通过。
