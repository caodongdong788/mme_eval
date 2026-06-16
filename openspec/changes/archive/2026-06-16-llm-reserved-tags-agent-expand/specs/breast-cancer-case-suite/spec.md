## MODIFIED Requirements

### Requirement: benchmark 必须含 agent 多轮专题

系统 MUST 在 `cases/breast_cancer/agent.yaml` 提供至少 **8** 道 `score_profile=agent` 多轮用例，rubric MUST 含 `inquiry_completeness` 以驱动 agent profile 的 inquiry 维度计分。

#### Scenario: agent 专题至少 8 条

- **WHEN** 加载 breast_cancer 套件
- **THEN** MUST 至少 8 条 `score_profile=agent` 用例
