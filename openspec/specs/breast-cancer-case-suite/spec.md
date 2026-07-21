# Breast Cancer Case Suite

## Purpose

约束乳腺癌正式评测 Case 的存放、审核与示例隔离，确保历史 Case 不会被重新加载。新 Case 必须使用唯一的 YAML v2 契约，并在正式运行前完成临床审核。

## Requirements

### Requirement: 正式套件必须由新 Case 提供

仓库 MUST NOT 保留历史乳腺癌 Case。新的正式 Case MUST 放入 `cases/benchmark/`、使用 YAML v2，并 MUST 在投入评测前经临床专家审核。

#### Scenario: 当前尚未提供新 Case

- **WHEN** `cases/benchmark/` 为空或不存在
- **THEN** `medeval validate` MUST 成功报告 0 条正式 Case，而不得回退加载示例或历史 Case

### Requirement: 示例不得进入正式评测

`cases/examples/` MUST 只用于说明 YAML v2 结构，并 MUST 由默认配置排除。

#### Scenario: 仓库仅有示例

- **WHEN** 默认配置执行 Case 加载
- **THEN** 示例 MUST NOT 出现在正式 Case 列表
