# Evaluation CLI

## Purpose

定义命令行在纯 v2 配置和固定八维评分下的校验、执行与重判能力。旧 Judge、评分档和 Case 字段必须在入口处直接失败，不能悄然降级。

## Requirements

### Requirement: CLI 必须只接受新配置

CLI MUST 从 typed `config.yaml` 装配 `eight_dimension` 与 `guideline` 两个 Judge；未知或旧 Judge、旧评分配置 MUST fail fast。

#### Scenario: 配置包含旧 Judge

- **WHEN** `judges` 中出现未声明的旧 key
- **THEN** `medeval validate` MUST 返回配置校验错误

### Requirement: CLI 必须支持校验、列举、执行和重判

CLI SHALL 提供 `validate`、`list-cases`、`run`、`rejudge` 与 `prune`。`rejudge` MUST 复用冻结 trace，MUST NOT 重新调用被测 bot。

#### Scenario: 校验无正式 Case

- **WHEN** 配置合法但 include 下没有正式 Case
- **THEN** `validate` MUST 成功并明确显示 0 条

### Requirement: Run 级门槛必须使用新命名

Run 级门槛 MUST 仅支持 `medical_safety_pass_rate` 与 `overall_pass_rate`，且 MUST NOT 提供按旧类型或评分档筛选的 CLI 参数。

#### Scenario: 医学安全性通过率未达标

- **WHEN** 实际安全通过率低于配置值
- **THEN** run 命令 MUST 以非零状态结束并保留报告产物
