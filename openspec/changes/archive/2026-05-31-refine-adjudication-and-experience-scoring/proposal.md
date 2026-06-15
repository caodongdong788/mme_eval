## Why

`add-semantic-rule-adjudicator` 与 `redesign-scoring-modules` 落地后，真实跑批暴露三类「报告看不清 / 口径偏紧」的问题：

1. **红旗用例的字面误杀无法被救回**：裁决器原设计对 `red_flag_triage != none` 的用例直接跳过救回、只标 `needs_human_review`。但红旗用例最容易出现「立即拨打120前往医院」被 `.{0,6}` 正则卡掉、或禁词出现在 bot 转述用户问句里这类纯字面误判，却因为安全闸完全得不到复核。实际安全已由 `hard_gate.*`（裁决器永不触碰）独立兜底，没必要连带禁掉规则层的语义救回。
2. **裁决器默认关闭**，导致大量字面误判（如「并不是切得越多就越安全」命中禁词）在默认配置下根本不过二次复核。
3. **体验软分与救回结果在报告里不透明**：体验失分只给一条「LLM 软分 3/4」总和，看不出扣在哪个维度；被裁决器救回的规则项则完全无痕，无法复盘「这条规则/正则是不是该优化」。此外不同用例的 LLM 体验维度缺乏统一评分基准，打分主观漂移。

顺带把两处对话流水 Excel 的查看体验问题定稿：固定栏占满前缀列挤掉对话明细、`transcripts.xlsx` 在 `outputs/` 常驻冗余。

## What Changes

- **红旗用例也走语义救回**：移除「红旗跳过救回」安全闸，所有 `rule.*` 失败用例（含红旗）一律尝试语义救回；红旗用例额外标记 `needs_human_review`，救回结果交人工二次确认。安全由 `hard_gate.*` 独立保证不受影响。
- **裁决器默认开启**（`enabled: true`）：默认让所有规则失败用例都过一道语义复核；显式关闭时行为与未引入该能力前完全一致。
- **体验软分逐维度归因**：每个 `score < max` 的 `llm.*` verdict 单独产出一条扣分理由（维度名 + 得分/满分 + LLM 简短理由），写入 `score_deductions`，不再只给软分总和。
- **救回项在报告留痕**：被裁决器救回的 `must_have` / `must_not_have` 不扣分，但在 `score_deductions` 追加「已救回」标注（含裁决理由），便于复盘规则口径。
- **LLM 体验维度默认评分锚点（方案 A）**：为 6 个体验维度内置 0..max 逐档默认标准，用例未写 `points` 时注入 prompt，提升打分一致性与可解释性；锚点表纳入 `LLMJudge.fingerprint()`。
- **对话流水固定栏改到「评级」列**：`freeze_panes` 落在评级列下一列，扣分原因/轮数/耗时/对话明细参与横向滚动，腾出屏宽看长对话。
- **`transcripts.xlsx` 改为飞书导入的中间产物**：发布成功后删除本地文件；仅在飞书关闭或发布失败时保留作兜底。

## Capabilities

### Modified Capabilities
- `judging-pipeline`: 红旗用例规则失败也走语义救回但标记待人工复核；裁决器默认开启；新增 LLM 体验维度默认评分锚点（方案 A）。
- `reporting`: 体验软分逐维度归因 + 救回项「已救回」标注写入 `score_deductions`；对话流水固定栏改到「评级」列；`transcripts.xlsx` 改为飞书导入中间产物（发布成功即删本地）。

## Impact

- 代码：`medeval/judges/semantic_adjudicator.py`（移除红旗安全闸早退、保留 `needs_human_review`）、`medeval/judges/llm.py`（默认锚点表 + `_format_rubric` 回退 + prompt 指令 + fingerprint）、`medeval/reporter/scoring.py`（体验逐维度扣分 + 救回标注）、`medeval/reporter/excel_transcript.py`（冻结列）、`medeval/cli.py`（发布成功删本地 xlsx）、`config.yaml`（裁决器默认 true）。
- 测试：`tests/test_semantic_adjudicator.py`、`tests/test_weighted_grading.py`、`tests/test_excel_transcript.py`、`tests/test_judge_fingerprint.py`（更新 `EXPECTED_FINGERPRINTS["llm_default"]`）。
- 兼容性：裁决器关闭时行为不变、历史 `report.json` 仍可加载；`LLMJudge` fingerprint 因锚点 + prompt 变化而漂移，已同 PR 更新基线。`transcripts.xlsx` 不再常驻 `outputs/`，对话流水以飞书在线表格为准。
- 安全：裁决器仍 MUST NOT 触碰任何 `hard_gate.*`；红旗急诊分诊判定始终由 HardGate 独立兜底，救回仅作用于 `rule.*`。
