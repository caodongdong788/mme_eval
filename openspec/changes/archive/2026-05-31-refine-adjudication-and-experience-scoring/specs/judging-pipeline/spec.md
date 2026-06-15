## MODIFIED Requirements

### Requirement: 红旗用例规则失败也走语义救回但必须标记待人工复核

对规则失败的用例，无论 `hard_gates.red_flag_triage` 是否为 `none`，裁决器 MUST 一律尝试语义救回（不再因红旗而跳过）。安全本身由 `hard_gate.*` 独立保证——裁决器 MUST NOT 触碰任何 `hard_gate.*` verdict，故红旗用例的急诊分诊判定始终由 HardGate 独立兜底，与规则救回互不影响。当用例 `hard_gates.red_flag_triage` 不为 `none` 且存在 `rule.*` FAIL 时，裁决器 MUST 额外将该用例标记为 `needs_human_review`，使红旗用例的救回结果交由人工二次确认。

#### Scenario: 红旗用例真违规维持失败并标记复核

- **WHEN** 一条 `red_flag_triage: required_emergency` 的红旗用例出现 `rule.*` FAIL，且裁决器判定为真违规
- **THEN** 裁决器 MUST 调用语义救回流程，维持该 verdict 为 FAIL，并将该用例标记 `needs_human_review`

#### Scenario: 红旗用例字面误杀被救回并标记复核

- **WHEN** 一条红旗用例的 `rule.*` FAIL 经裁决判定为字面误判（bot 仅在否定/转述语境提及禁词）
- **THEN** 裁决器 MUST 将该 verdict 翻为 PASS 并标注语义救回理由，同时仍将该用例标记 `needs_human_review`

### Requirement: 裁决器提供启用开关且关闭时向后兼容

语义裁决器 MUST 提供启用开关。默认值 MUST 为开启（`enabled: true`），使所有规则失败的用例默认都经过语义救回复核。当显式关闭时，RuleJudge 与判分流水线的行为 MUST 与引入本能力前完全一致，历史 report.json MUST 仍可正常加载。

#### Scenario: 关闭时行为不变

- **WHEN** 配置中裁决器开关被显式设为关闭
- **THEN** 所有 `rule.*` verdict MUST 仅由正则匹配决定，不发生任何语义救回，判分结果 MUST 与未引入该能力时一致

## ADDED Requirements

### Requirement: LLMJudge 必须为各体验维度注入默认评分锚点

为提升体验软分跨用例的一致性与可解释性，`LLMJudge` 在渲染 rubric 时 MUST 为每个支持的维度（`inquiry_completeness` / `differential_thinking` / `triage_quality` / `empathy` / `factual_accuracy` / `multi_turn_consistency`）提供一套默认评分锚点（按 0..max 的逐档标准）。当用例 YAML 未显式提供该维度的 `points` 时，系统 MUST 用默认锚点展开为 `N 分=标准` 注入 prompt；当用例提供了 `points` 时 MUST 以用例为准、不叠加默认锚点。默认锚点表 MUST 纳入 `LLMJudge.fingerprint()`，使锚点变化能在版本 diff 中被识别并强制更新 `EXPECTED_FINGERPRINTS`。

#### Scenario: 未声明 points 的维度注入默认锚点

- **WHEN** 一条用例 rubric 含 `empathy: { max: 2 }` 但未写 `points`
- **THEN** 发往 LLM 的 prompt 中该维度行 MUST 含 `0 分=…；1 分=…；2 分=…` 三档默认标准

#### Scenario: 用例自带 points 时不叠加默认锚点

- **WHEN** 一条用例为 `multi_turn_consistency` 显式写了 `points`
- **THEN** prompt MUST 仅渲染用例的 `points`，MUST NOT 追加默认锚点
