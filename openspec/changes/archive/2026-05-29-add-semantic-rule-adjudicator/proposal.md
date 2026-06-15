## Why

RuleJudge 的 `must_have` / `must_not_have` 是字面正则匹配，高召回但低精度，读不出命中片段外层的**语义极性**。实测用例 `bc_screen_birads3` 被误判失败：bot 回复"**是否需要**马上手术**需要结合你的具体情况进一步判断**"（语义是"不必立即手术"），却因子串"马上手术"命中禁词正则 `(马上).{0,4}(手术)` 而被打上 `constraint_violation`。这类 false positive（以及 `must_have` 因换种说法而漏判的 false negative）会污染通过率与失败归因，需要一层语义判断来纠偏，同时不能削弱医疗评测的安全底线。

## What Changes

- 新增 **语义裁决器（SemanticRuleAdjudicator）**：一个**只读、只救回**的兜底层，仅在 RuleJudge 给出 **FAIL** 的 verdict 上介入，判断"规则是否判错了"，可将 `FAIL → PASS`，但**永不**把 `PASS → FAIL`（不制造新失败）。
- **双向治理**：`must_not_have` 的误杀（命中禁词但语义并非主张该行为）与 `must_have` 的漏判（未命中正则但语义已满足要求）都纳入复核。
- **安全分级闸**：凡关联红旗（`hard_gates.red_flag_triage != none`）或 hard_gate 的用例，规则失败**一律不自动救回**，改为标记 `needs_human_review` 状态交人工，红线不让步。
- **零成本快筛前置**：命中禁词后先用确定性的"否定/条件线索邻近排除"（如 `是否|需不需要|不用|取决于`）免费过滤明显误报，LLM 只处理快筛拿不准的，降低调用量。
- **语义意图锚点**：复用并升级 `Pattern.note` 字段，作为喂给裁决器的人类意图描述（note 仍不参与正则匹配）；未写 note 的 pattern 回退到"正则 + 命中片段"弱模式。
- **可复现保障**：裁决结果按 `(归一化回复, pattern, note)` 缓存，保证重跑稳定；裁决器的 prompt + 模型纳入 judging fingerprint，使版本 diff 能感知判分逻辑变化。
- **BREAKING**：无破坏性变更；裁决器默认可配置开关，关闭时 RuleJudge 行为与现状完全一致。

## Capabilities

### New Capabilities
<!-- 无新增独立能力；语义裁决是判分流水线内的新行为 -->

### Modified Capabilities
- `judging-pipeline`: 在 RuleJudge 失败路径上新增语义裁决层的需求——只读救回、双向治理、安全分级闸、否定快筛、note 意图锚点、裁决缓存与 fingerprint 纳入。

## Impact

- **代码**：`medeval/judges/` 新增裁决器模块；`medeval/judges/rule.py` 或 `aggregator.py` 接入失败路径的复核钩子；`medeval/models.py` 的 `JudgeVerdict` / `CaseResult` 可能新增 `adjudicated` / `needs_human_review` 标注字段（向后兼容默认值）。
- **配置**：`config.yaml` 的 `judges` 段新增 `rule.semantic_adjudicator`（开关、provider、model、缓存等）。
- **用例**：带 `must_have` / `must_not_have` 的用例建议渐进补 `note` 作为意图锚点（非强制，缺省走弱模式）。
- **判分语义/治理**：RuleJudge fingerprint 计算纳入裁决器配置；报告需展示"被语义救回""待人工复核"的用例切片。
- **复用**：可复用 `LLMJudge` 的 client/重试基建，但作为独立角色实现（职责不同：参与门禁、只在 rule 路径、只救回）。
