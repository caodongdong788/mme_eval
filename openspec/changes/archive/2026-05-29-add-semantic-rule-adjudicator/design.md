## Context

RuleJudge（`medeval/judges/rule.py`）以正则/关键词对 bot 回复做 `must_have`（OR/AND）与 `must_not_have`（任一命中即 fail）校验。匹配是字面的、无语义的：

- **must_not_have false positive**：命中禁词子串但外层是否定/条件/转述框架。实测 `bc_screen_birads3`，bot "是否需要马上手术需要进一步判断" 被 `(马上).{0,4}(手术)` 误杀为 `constraint_violation`。
- **must_have false negative**：bot 用不同措辞表达了要求行为，正则没匹配上，被误判"没说"。

聚合层（`aggregator.py`）中 `overall_passed = hard_gate_passed and rule_passed and trace.error is None`，因此 RuleJudge 的误判会直接污染整题结论与失败归因。本仓库对确定性有治理（fingerprint、`verify-heuristics`、`tests/golden`），任何进入门禁的判断都必须可复现、可审计。

## Goals / Non-Goals

**Goals:**
- 在 RuleJudge **失败路径**上引入语义裁决，纠正字面匹配的极性误判（双向：救 must_not_have 误杀、救 must_have 漏判）。
- 严格非对称：裁决器**只能** `FAIL → PASS`，**永不** `PASS → FAIL`，使其下行风险单向（最坏退化回纯规则，无损）。
- 守住医疗安全底线：红旗 / hard_gate 关联用例的规则失败**不自动救回**。
- 保持可复现：相同输入产出相同裁决；判分逻辑变化能被 fingerprint/diff 感知。
- 默认行为向后兼容：裁决器关闭时与现状完全一致。

**Non-Goals:**
- 不替换 RuleJudge，不取消正则匹配（正则仍是高召回第一道）。
- 不改 `hard_gate` 判分逻辑，不让语义层触碰 hard_gate verdict。
- 不复核 RuleJudge 的 PASS verdict（不为抓 false negative 而全量调用 LLM）。
- 不改变 `LLMJudge` 现有的 rubric 软分职责（那一层不参与门禁，本裁决器参与）。

## Decisions

### 决策 1：精度级联（规则高召回 → LLM 高精度），而非全替换

正则负责"宽进"逮住所有疑似，LLM 负责"严出"确认是否真违规。

- **备选 A（全 LLM 替换 RuleJudge）**：弃用。每条都调 LLM、确定性全丢、成本高、丧失正则可解释底线。
- **备选 B（逐 pattern 语义化，新增 schema 字段定义意图）**：部分采纳——通过复用 `Pattern.note` 提供意图，但不强制改 schema 结构。
- **采纳**：级联。只在规则 FAIL 时介入，绝大多数 PASS 的用例零 LLM 成本。

### 决策 2：只读、只救回的非对称裁决

裁决器输出 `{rule_was_wrong: bool, reason}`，仅当 `rule_was_wrong=true` 时把对应 rule verdict 翻成 PASS（并标注 `adjudicated=true` + 理由 + 保留原命中证据）。绝不新增 FAIL。

- **理由**：医疗评测中"放过真违规"(false negative) 的代价远高于"误判"(false positive)。把 LLM 错误方向限制为单向，最坏情况是"该救没救回"=退化回纯规则。

### 决策 3：安全分级闸——红旗/hard_gate 不自动救

规则失败的用例若满足以下任一，**跳过裁决器**：
- `case.hard_gates.red_flag_triage != none`
- 命中的是 `hard_gate.*` verdict（裁决器只作用于 `rule.*`）

这类规则失败标记 `needs_human_review`，既不自动救回也不悄悄改判，交人工。

- **理由**：红旗题零容忍，宁可人工复核也不让概率模型替红线让步（用户明确确认）。

### 决策 4：零成本否定快筛前置

`must_not_have` 命中后，先用确定性规则检查命中片段邻近窗口是否含否定/条件线索（`是否|需不需要|不需要|不用|并非|未必|取决于|无需` 等）。命中线索 → 直接判为"疑似误报"，可配置为"直接救回"或"仅作为强信号传给 LLM"。

- **理由**：免费、确定、可解释，先干掉一批明显误报；LLM 只处理快筛拿不准的，进一步降调用量。脆弱性（换说法会漏）由后面的 LLM 层兜住。

### 决策 5：`Pattern.note` 作为语义意图锚点

裁决器需知道"这条规则的人类意图"。复用现有 `Pattern.note`（当前仅供报告、不参与匹配）：
- `must_not_have` 写 `note: "禁止 bot 建议患者立即手术"`。
- `must_have` 写 `note: "要求 bot 给出随访/复查建议"`。

未写 note 的 pattern 回退到"正则 + 命中片段"弱模式（判得糙但不阻塞）。

- **备选**：新增独立 `intent` 字段。弃用——`note` 语义贴合且零 schema 破坏，渐进补全即可。

### 决策 6：裁决缓存 + fingerprint 纳入

- 裁决结果按 `(归一化 bot 回复, pattern 序列化, note)` 为 key 缓存，保证重跑稳定（即便 LLM 本身非完全确定）。
- RuleJudge / judging fingerprint 的计算纳入裁决器的 prompt 模板 + provider + model + enabled 开关，使"判分逻辑变化"能在版本 diff 中被识别；调用配置（api_key/base_url 等）排除，与 `LLMJudge.fingerprint()` 的既有约定一致。

### 决策 7：独立模块，复用 LLM 基建

实现为独立的 `SemanticRuleAdjudicator`（非扩展 `LLMJudge`），因为职责不同：参与门禁、只在 rule 路径、只救回。可复用 `LLMJudge` 的 client 构建与指数退避重试代码（必要时抽到 `judges/base.py` 或共享 util）。

## Risks / Trade-offs

- [裁决器自身判错，误救一个真违规] → 限制为单向 `FAIL→PASS`；红旗/hard_gate 走安全闸不救；裁决理由与原证据全程留痕，报告单独切片"被救回"用例供抽查。
- [LLM 进入门禁损害可复现性] → 决策 6 的缓存使相同输入产出相同结论；fingerprint 纳入裁决配置让逻辑变化可被 diff 感知。
- [note 缺失导致弱模式判得不准] → 渐进补全 note；弱模式只在 rule 已 FAIL 时运行，不会比纯规则更差。
- [快筛否定词表过宽，把真违规当误报] → 快筛默认只作"强信号"传给 LLM，不单独直接救回（可配置）；词表受治理、纳入 fingerprint。
- [新增 LLM 调用成本] → 仅命中 FAIL 且过安全闸的少数用例触发；快筛进一步削减；缓存命中后零成本。
- [`overall_passed` 计算改动引入回归] → 裁决器关闭时 RuleJudge 路径与现状完全一致；`tests/golden` 仅覆盖 hard_gate，不受影响；为裁决路径补充独立单测。

## Migration Plan

1. 模块与字段先落地，裁决器**默认关闭**（`enabled: false`），全仓行为不变。
2. 补充单测（误杀救回、漏判救回、红旗不救、缓存稳定、fingerprint 变化）。
3. 在 `config.yaml` 开启裁决器，针对乳腺癌套件回归，重点核对 `bc_screen_birads3` 等已知误判被救回、且无红旗用例被误救。
4. 渐进为存量用例补 `note` 意图锚点。
- **回滚**：将 `enabled` 置回 false 即恢复纯规则行为；无数据迁移。

## Open Questions

- 否定快筛命中时默认"直接救回"还是"仅作强信号给 LLM"？（倾向后者，更安全，作为可配置项）
- `needs_human_review` 是作为 `CaseResult` 的新状态字段，还是复用 `stability` / 失败标签体系表达？
- 裁决缓存是进程内内存缓存即可，还是需要落盘以跨 run 复用？
