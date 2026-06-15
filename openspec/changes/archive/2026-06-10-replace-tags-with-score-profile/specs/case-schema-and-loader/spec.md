## MODIFIED Requirements

### Requirement: 系统必须以 Pydantic 模型定义所有用例字段

系统 MUST 为每一条 YAML 用例提供严格的 Pydantic v2 Schema，覆盖 sample_id、scenario / sub_scenario、level、population、difficulty、**score_profile**、source、turns、expected_behavior、hard_gates、rubric、failure_tags_candidates、notes 等字段。`score_profile` MUST 为受控枚举 `default` / `red_flag` / `adversarial` / `knowledge` / `rehab`，默认 `default`；若 YAML 误写为列表 MUST 只取第一个元素。Schema MUST NOT 再声明 `tags` 字段；历史 YAML 中的 `tags` key MUST 导致校验失败（非 silent ignore）。

#### 场景:score_profile 决定评分 profile

- **当** 用例 `score_profile: knowledge`
- **那么** `resolve_profile()` MUST 返回 config 中 `profiles.knowledge` 的权重与 pass_rule

#### 场景:加载非法 tags 必须失败

- **当** YAML 仍含 `tags: [...]`
- **那么** Pydantic 校验 MUST 失败
