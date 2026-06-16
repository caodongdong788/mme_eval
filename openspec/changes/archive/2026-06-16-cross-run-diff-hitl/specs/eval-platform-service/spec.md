## MODIFIED Requirements

### Requirement: 人工审核队列

系统 SHALL 提供按 run 的人工审核队列。某 run 的用例 MUST 入队当且仅当满足任一：
(a) `case_result.needs_human_review = true`；(b) `release_passed = false`（原因记 `release_failed`）；
(c) 红旗题且 `release_passed = false`（额外标注 `red_flag_failed`）；(d) 任一 verdict 的
`score_dispersion` ≥ 0.5（原因记 `high_dispersion`）；(e) 与可比基线 run 对比存在剧烈变化（原因记 `cross_run_diff`）。
`GET /api/runs/{run_id}/review-queue` 行为不变（返回结构含 `reasons`）。

可比基线 run MUST 满足：当前 run 的 `diff_against_run_id` 指向的成功 run，或自动解析的上一成功同 benchmark run；
且双方 `judge_fingerprints` 相等。剧烈变化 MUST 指以下任一：
`release_passed` / `hard_gate_passed` / `gate_passed` 与基线不同；`|composite_score 差| ≥ 0.25`；
任一 `dimension_scores` 键的差 ≥ 0.15。

#### Scenario: 跨版本综合分骤降入队

- **WHEN** 当前 run 与可比基线 run 中同一 `sample_id` 的 `release_passed` 均为 true，但综合分从 0.92 降至 0.65
- **THEN** 该用例 MUST 出现在 review-queue，且 `reasons` MUST 含 `cross_run_diff`

#### Scenario: 判分尺子不可比时跳过

- **WHEN** 基线 run 与当前 run 的 `judge_fingerprints` 不一致
- **THEN** 系统 MUST NOT 因跨版本对比将该用例入队（其它入队规则仍适用）
