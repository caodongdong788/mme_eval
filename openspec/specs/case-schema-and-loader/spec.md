# Case Schema and Loader

## Purpose

定义唯一合法的 Case YAML v2 结构及确定性加载行为。加载器必须严格拒绝旧字段、未知字段、重复标识和不合法的指南绑定，不提供转换或回退分支。

## Requirements

### Requirement: 正式 Case 只接受 YAML v2

正式 Case MUST 声明 `schema_version: "2.0"` 或 `"2.1"`、`sample_id`、`scenario`、`level`、`turns` 与 `evaluation`。`2.0` 用于兼容历史 Case，`2.1` 支持账号初始化与运行验收；未知字段（包括通用 `metadata`）MUST 被拒绝。

#### Scenario: 旧结构被拒绝

- **WHEN** YAML 未声明 v2 或包含旧评分字段
- **THEN** loader MUST fail fast，Case 不得进入 Runner

### Requirement: evaluation 必须表达八维补充标准和指南

`evaluation.dimension_criteria` 的键 MUST 取自固定八维；每个值 MUST 是非空字符串列表。每条 guideline MUST 含 Case 内唯一 `id`、非安全目标维度、非空 `criterion` 与严格整数 `max_score`（1～5）。

#### Scenario: 指南绑定医学安全性

- **WHEN** guideline 的 `dimension` 是 `medical_safety`
- **THEN** Schema MUST 拒绝该 Case

### Requirement: 加载结果必须确定

loader MUST 检查全局 `sample_id` 唯一性，并 MUST 按稳定路径顺序加载 include 命中的 YAML，同时排除 exclude 路径。

#### Scenario: 重复 sample_id

- **WHEN** 两个正式 Case 使用相同 `sample_id`
- **THEN** loader MUST 报错并指出重复 ID
