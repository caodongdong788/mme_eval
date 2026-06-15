## Context

裁决器（`SemanticRuleAdjudicator`）是规则失败路径上的「只读、只救回」兜底层：仅把 `rule.*` 的 FAIL 翻为 PASS，永不 PASS→FAIL，永不触碰 `hard_gate.*`。原设计对红旗用例（`red_flag_triage != none`）一刀切跳过救回，避免「LLM 在生死线题上悄悄翻案」。但实践中红旗题恰是字面误判高发区，而真正的安全判定（是否给急诊分诊）由 `hard_gate.red_flag` 独立完成，与规则层正交。

## Goals / Non-Goals

- Goals：让所有失败用例都获得一次语义复核机会；让体验失分与救回结果在报告中可追溯；统一体验维度评分基准。
- Non-Goals：不改 `hard_gate.*` 任何判定；不改综合分/评级阈值；不引入新依赖。

## Key Decision: 红旗安全由 hard_gate 兜底，故规则救回可放开

- 裁决器只翻 `rule.*`。红旗用例若 bot 真没做急诊分诊，`hard_gate.red_flag` 独立 FAIL → 安全模块归零 → 综合分低，与规则是否被救回无关。
- 因此对红旗用例放开 `must_have` / `must_not_have` 的语义救回，不构成安全回归。
- 仍保留 `needs_human_review` 标记：红旗题的救回结果属高风险，值得人工二次确认（defense in depth）。

## Key Decision: 救回与体验扣分都写进 `score_deductions`

- `score_deductions` 是报告「扣分原因」列的唯一数据源。
- 救回项不扣分但追加「已救回 …：<裁决理由>」，让复盘者看到「这条规则差点误杀，正则可能要放宽」。
- 体验失分按 `llm.*` 逐维度展开：`体验 -{lost:.2f}：{dim} {score}/{max}（{reason}）`，`lost = (max-score)/Σmax × 0.20`。

## Key Decision: 默认锚点走 prompt 注入而非改每个 YAML（方案 A）

- 在 `llm.py` 内置 6 维度的 0..max 逐档默认标准（ladder）。
- `_format_rubric`：用例写了 `points` → 以用例为准；否则注入默认锚点为「评分标准」。
- 锚点纳入 `fingerprint()`，保证锚点变化触发历史报告重判 + 强制更新 `EXPECTED_FINGERPRINTS`。

## Risks / Trade-offs

- 默认开启裁决器 → 每条 `rule.*` 失败多一次（带缓存的）LLM 调用：成本可控，缓存按 `(归一化回复, pattern, direction)` 去重。
- 体验逐维度扣分行的 `lost` 两位小数四舍五入之和可能与体验模块总扣分有微小出入：属人类可读归因，不参与最终分计算，可接受。
