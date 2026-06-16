# Proposal: cross-run-diff-hitl

## 背景

P3 路线图「跨版本 diff 自动入 HITL」：两次评测 run 对比时，若某题相对基线 run 综合分或 gate 状态剧烈变化，应自动进入人工审核队列。当前仅支持同 run 内 `score_dispersion≥0.5` 入队。

## 目标

- 评测落库时记录 `diff_against_run_id`（来自 `resolve_diff_target` 解析的上一版 outputs）。
- 人工审核入队规则扩展：与可比基线 run 逐题对比，满足任一 MUST 入队并标注 `cross_run_diff`：
  - `release_passed` / `hard_gate_passed` / `gate_passed` 翻转；
  - `|composite_score 差| ≥ 0.25`；
  - 任一维度 `dimension_scores` 差 ≥ 0.15。
- 仅当两次 run **判分尺子可比**（同 benchmark、`judge_fingerprints` 相等）时启用；否则跳过。

## 范围

- 平台侧 `server/**` + 测试；**不修改** `medeval` 判分内核。
- 前端可选：入队原因中文映射（若已有展示位）。

## 非目标

- 不自动写 `needs_human_review` 回判分字段；
- 不做跨 run diff 的独立 API 扩展（沿用现有 `/diff`）。
