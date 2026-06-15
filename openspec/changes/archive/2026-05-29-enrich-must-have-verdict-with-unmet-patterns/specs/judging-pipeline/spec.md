## ADDED Requirements

### Requirement: JudgeVerdict 必须新增 unmet_patterns 字段承载未命中的期望模式清单

`JudgeVerdict` MUST 新增字段 `unmet_patterns: list[Pattern]`，默认 `Field(default_factory=list)`（向后兼容历史 `report.json`）。该字段用于结构化表达"该 verdict 失败时，case 期望命中但未被命中的模式集合"，每项必须是与 `case.expected_behavior.must_have` 同构的 `Pattern` 对象（`keyword: str | None` 或 `regex: str | None`）。

只有 RuleJudge 在 `rule.must_have` verdict 上 MUST 填充该字段；其它 judge（HardGate、LLM、未来扩展）以及 `rule.must_not_have` verdict MUST 保持 `unmet_patterns = []`。判定通过的 verdict 也 MUST 保持 `unmet_patterns = []`，避免冗余存储 case 数据。

#### 场景:历史 JSON 反序列化默认空 list

- **当** 加载一份不含 `unmet_patterns` 字段的旧 `report.json`
- **那么** 每条 verdict 的 `unmet_patterns` 必须默认值为 `[]`，不抛错

#### 场景:其它 judge 保持空 unmet_patterns

- **当** HardGateJudge 因为缺免责声明返回 `hard_gate.disclaimer` fail
- **那么** 该 verdict 的 `unmet_patterns` 必须为 `[]`（HardGate 不通过该字段表达失败原因）

### Requirement: RuleJudge 必须在 must_have 失败时填充 unmet_patterns

`RuleJudge._check_must_have` 在 verdict 失败时 MUST 填充 `unmet_patterns`，填充规则按模式分支：

- OR 模式（默认，`must_have_all` 缺省或 false）全部未命中时 → `unmet_patterns = case.expected_behavior.must_have`（完整列表，按原序）。
- AND 模式（`must_have_all=true`）部分或全部未命中时 → `unmet_patterns = missing` 子集（即未命中的那部分 `Pattern`，按原序）。
- 通过时（OR 至少命中一条 / AND 全部命中）→ `unmet_patterns = []`。

`reason` 字段 MUST 保持人话总结，区分 OR / AND 模式：OR 失败时为"全部 must_have 均未命中（期望任一命中）"，AND 失败时为"must_have 部分未命中（要求全部命中）"。具体未命中模式 MUST 不再以字符串拼接形式塞入 `reason`，而是统一通过 `unmet_patterns` 暴露。

`RuleJudge.fingerprint()` MUST 保持原值不变（仅扩展 verdict 输出，不改变判定逻辑），保证历史报告 diff 不出现 fingerprint 误警告。

#### 场景:OR 模式全部未命中时填充全部期望模式

- **当** case `must_have: [{keyword: "升糖"}, {keyword: "粗粮"}, {regex: "(白粥|油条).{0,12}(不建议|不推荐)"}]`，bot 回复未命中任一
- **那么** 返回的 `rule.must_have` verdict 必须 `passed=false`、`reason` 含"全部 must_have 均未命中"、`unmet_patterns` 长度为 3 且按原序包含三个 `Pattern` 对象（前两个 keyword、第三个 regex）

#### 场景:AND 模式部分未命中时只填充缺失子集

- **当** case `must_have_all=true` 且 `must_have: [{keyword:"A"},{keyword:"B"},{keyword:"C"}]`，bot 回复只命中 B
- **那么** 返回的 verdict `passed=false`、`reason` 含"must_have 部分未命中（要求全部命中）"、`unmet_patterns` 必须等于 `[Pattern(keyword="A"), Pattern(keyword="C")]`（按原序剔除已命中项）

#### 场景:通过时 unmet_patterns 必须为空

- **当** OR 模式 case `must_have` 中至少一条命中
- **那么** 返回的 `rule.must_have` verdict `passed=true`、`unmet_patterns` 必须为 `[]`

#### 场景:case 无 must_have 声明时 unmet_patterns 必须为空

- **当** case `expected_behavior.must_have == []`
- **那么** RuleJudge 直接返回 `passed=true, reason="N/A"` 的 verdict，`unmet_patterns` 必须为 `[]`

#### 场景:fingerprint 在新旧版本之间保持一致

- **当** 同一份 `RuleJudge(normalize=true)` 在扩展 `unmet_patterns` 前后被调用
- **那么** `fingerprint()` 返回值必须完全一致，让历史 `report.json` 与新 `report.json` 之间的 `diff_runs` 不触发判官版本警告
