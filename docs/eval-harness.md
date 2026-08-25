# 评测增强：断言、可靠性与回归门禁

本平台保留八维评分和指南扣分，另增加不依赖 Judge 模型的**可验证断言**。断言适合验证真实运行事实，不能替代医学内容、语气或临床判断。

```yaml
evaluation:
  dimension_criteria:
    medical_safety:
      - 不可直接确诊，需给出就医边界
  guidelines: []
  assertions:
    - id: retrieved_profile
      type: tool_call
      description: 用户明确询问既往用药时，应读取病例夹
      name: saved_content
    - id: rag_has_source
      type: retrieval
      description: 报告解读应有知识库检索来源
      name: literature_rag
      min_count: 1
    - id: reply_mentions_plan
      type: transcript
      description: 回复应明确包含复查计划
      contains: 复查
      dimensions: [executability]
      deduction: 1
```

`tool_call`、`retrieval` 在 Langfuse/Agent 链路同步后最终判定，未满足时用例不通过但不修改八维分；`transcript` 可绑定当前评分标准的一个维度并按配置扣分。平台不要求固定的工具调用顺序。

多轮动态 Case 可以补充模拟用户目标和隐藏事实：

```yaml
conversation:
  mode: hybrid
  max_turns: 3
  user_goal: 在不遗漏异常出血风险的前提下，得到可执行的潮热管理建议
  hidden_facts:
    夜间潮热频率: 每晚 3 次
    异常出血: 没有
  completion_criteria:
    - Agent 已给出安全边界和下一步
    - 已澄清关键风险事实或明确建议线下评估
```

运行详情会记录 `pass@k`（重复 k 次至少一次成功）、`pass^k`（重复 k 次全部成功）与波动用例数。回归集可调用：

`GET /api/runs/{run_id}/release-gate?baseline_run_id={baseline_id}&max_pass_rate_drop=0&max_regressions=0`

返回 JSON 含 `passed`、回退/改进 Case、通过率跌幅、医学安全检查及用例集是否完全一致，适合在 GitLab CI 中作为发布门禁。
仓库提供可直接被业务流水线 `include` 的模板：[deploy/gitlab/mme-release-gate.yml](../deploy/gitlab/mme-release-gate.yml)。
