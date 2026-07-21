# Evaluation Platform Dashboard

## Purpose

规定平台前端如何展示、编辑和比较固定八维与指南部分分评测结果。所有页面必须共享同一组维度名称、三端 45 分制和医学安全性底线语义。

## Requirements

### Requirement: 平台必须展示统一评测标准页

前端 MUST 提供评测标准页，展示八维名称、所属角色端、评分范围、三端归一、45 分评级阈值、医学安全归零和指南扣分公式。

#### Scenario: 打开评测标准页

- **WHEN** 标准 API 返回数据
- **THEN** 页面 MUST 展示八个维度和三端各 15 分

### Requirement: Run 列表必须使用医学安全命名

Run 列表和总览 MUST 展示通过率、医学安全性失败数和稳定性，且 MUST NOT 使用旧评分术语。

#### Scenario: Run 有两个安全失败 Case

- **WHEN** `medical_safety_failed=2`
- **THEN** 列表 MUST 以危险样式显示 2

### Requirement: Case 详情必须展示完整新评分

Case 详情 MUST 展示原始八维、指南逐项得分/满分/证据、扣分后八维、三端分、45 分总分、评级和扣分原因。未知 label MUST 回退原始 key。

#### Scenario: 指南得 2/3

- **WHEN** Case 明细包含该指南结果
- **THEN** 页面 MUST 展示 `2 / 3` 及其绑定维度和理由

### Requirement: 判据编辑器必须只编辑 evaluation

Benchmark 和重判编辑器 MUST 只接受 Case v2 的 `evaluation.dimension_criteria` 与 `evaluation.guidelines`，保存失败 MUST 展示服务端结构化校验错误。

#### Scenario: 输入旧字段

- **WHEN** 用户保存包含旧评分字段的 YAML
- **THEN** 页面 MUST 展示 422 错误且不得显示保存成功

### Requirement: Pairwise 页面必须展示八维结果

Pairwise 汇总、逐题结果和人工校准 MUST 使用统一八维 key 与中文标签，并 MUST 把医学安全性低置信单独标识。

#### Scenario: 人工校准逐维胜方

- **WHEN** 用户打开校准弹窗
- **THEN** 弹窗 MUST 提供全部八个维度的 A/B/tie 选择
