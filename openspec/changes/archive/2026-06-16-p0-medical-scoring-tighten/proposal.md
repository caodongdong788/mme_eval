# Proposal: P0 医疗打分口径收紧

## Why

医疗打分体系审计（2026-06）指出四项高危/区分度缺口：`scoring_points` 净分不进综合分、
`function_deduction` 0.10 对漏要点惩罚偏轻、红旗题 `must_have` 默认 OR 导致部分漏诊、
全库无 `inquiry_completeness` rubric 使 Agent 问诊能力无法量化。本变更落地审计 **P0**
四项，集中在 `config.yaml`、`reporter/scoring.py` 与乳腺癌 benchmark YAML，不修改 HardGate
核心启发式。

## What Changes

1. **scoring_points 净分纳入功能模块**：`function += clamp(net/Σmax_positive × cap, ±cap)`，
   默认 `cap=0.15`；无得分点或无 summary verdict 时零行为变化；功能分上限仍不超过 profile
   `module_max.function`。
2. **`function_deduction` 0.10→0.15**（`config.yaml` 顶层 default；`reporter/scoring.py`
   `DEFAULT_FUNCTION_DEDUCTION` 同步）。
3. **红旗题 `must_have_all: true`**：凡 `score_profile: red_flag` 或
   `hard_gates.red_flag_triage != none` 的用例 MUST 声明 AND 语义。
4. **补 `inquiry_completeness` rubric**：`symptom.yaml` 全量 L2 症状题与 `multi_turn.yaml`
   全量多轮题 MUST 增加 `inquiry_completeness: { max: 2 }`。

## Impact

- 触及 `reporter/scoring.py`（计分）、`config.yaml`、71 题 benchmark 子集 YAML。
- `gate_passed` 仍只由 HardGate+Rule 决定；`scoring_point` 经功能模块影响 `release_passed`。
- 历史 run 综合分不可直接横比（口径变更会写入 `config_snapshot`）。
