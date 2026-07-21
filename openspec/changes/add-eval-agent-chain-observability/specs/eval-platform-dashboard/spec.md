## ADDED Requirements

### Requirement: Case 明细必须展示 Agent 全链路

平台 SHALL 在 Case 明细展示评测身份、账号重置结果、用户画像快照以及从 Langfuse 解析的 Agent/Generation/Tool 调用树；每个节点 MUST 可查看耗时、模型、Token、输入输出摘要与错误。

#### Scenario: Langfuse 同步成功

- **WHEN** Case 已成功同步 observations
- **THEN** 明细页按父子关系展示完整调用树并保留原始 Trace 跳转入口

#### Scenario: Langfuse 不可用

- **WHEN** Langfuse 未配置、暂未落盘或查询失败
- **THEN** 评测结果仍正常展示，链路区域明确显示同步状态且不影响评分
