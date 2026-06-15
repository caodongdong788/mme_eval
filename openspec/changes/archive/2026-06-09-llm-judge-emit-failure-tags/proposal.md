# Proposal: LLM 判官 emit 受控 FailureTag

## Why

`FailureTag` 词表里 `EMPATHY_MISS` / `DIFFERENTIAL_NARROW` / `MEDICAL_HALLUCINATION` /
`DIALOG_BREAK` 等成员**已预留但无任何 Judge emit**（meta 描述带"暂未由 Judge emit"后缀）。
LLMJudge 已逐维度产出 `llm.<dim>` verdict 并判 `passed`，语义层发现的"共情缺失/鉴别过窄/
医学幻觉/上下文断裂"却进不了受控失败归因，看板/报告统计不到这些语义失败。本变更激活这条链路，
让 LLM 层的发现像 HardGate/Rule 一样进入 `failure_tags` 聚合——零额外 API 成本（复用既有打分结果）。

## What Changes

- **维度→标签映射**：`LLMJudge` 在某维度 verdict `passed=False`（`score < max/2`）时，append 对应
  受控 `FailureTag`：`empathy→EMPATHY_MISS`、`differential_thinking→DIFFERENTIAL_NARROW`、
  `factual_accuracy→MEDICAL_HALLUCINATION`、`multi_turn_consistency→DIALOG_BREAK`、
  `inquiry_completeness→INQUIRY_INCOMPLETE`。`triage_quality` **故意不映射**（分诊归 HardGate，
  避免双重归因）。judge 未启用 / 调用失败 / 过线维度 MUST NOT emit 标签。
- **观测不否决**：emit 的标签是纯归因，MUST NOT 影响 `score`/`gate_passed`/`release_passed`
  （三根正交轴语义不变）；仅经既有 `reporter/aggregator` 流进看板失败分布。
- **fingerprint**：维度→标签映射纳入 `LLMJudge.fingerprint()`，使"判分逻辑变化"可被 diff 区分。
- **治理**：从被激活标签的 `_TAG_META` 去掉"暂未由 Judge emit"后缀，重跑
  `python -m medeval.docs.gen_failure_tags --write` 刷新 README 的 AUTO-GENERATED 区块（受单测守门）。

## Impact

- Affected specs: `judging-pipeline`（LLM 判官失败归因）
- Affected code: `medeval/judges/llm.py`、`medeval/models.py`（仅去 `_RESERVED_NOTE` 后缀，不增删枚举成员）、
  `README.md`（AUTO-GENERATED 区块由脚本刷新）
- 不动 `hard_gate.py`（无需 `verify-heuristics`）；对未启用 LLMJudge 的链路零行为变化。
