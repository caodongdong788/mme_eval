## MODIFIED Requirements

### Requirement: 人工审核队列

系统 SHALL 提供按 run 的人工审核队列。某 run 的用例 MUST 入队当且仅当满足任一：
(a) `case_result.needs_human_review = true`；(b) `release_passed = false`（原因记 `release_failed`）；
(c) 红旗题且 `release_passed = false`（额外标注 `red_flag_failed`）；(d) 任一 verdict 的
`score_dispersion` ≥ 0.5（原因记 `high_dispersion`）。`GET /api/runs/{run_id}/review-queue` 行为不变。

#### Scenario:高离散度用例入队

- **WHEN** 用例 `release_passed=true` 但某 `llm.*` verdict 的 `score_dispersion=0.6`
- **THEN** 该用例 MUST 出现在 review-queue，且 `reasons` MUST 含 `high_dispersion`

## ADDED Requirements

### Requirement: Run 人审校准一致性 API

系统 MUST 提供 `POST /api/runs/{run_id}/calibration`，接受上传的人审打分表（YAML/JSON），
与指定 run 的 `report.json` 对齐计算人机一致率（如 Cohen's kappa、逐维 Pearson 等），
MUST NOT 回写任何判分字段。

#### Scenario:校准成功返回度量

- **WHEN** 客户端上传合法人审表且 run 目录存在 `report.json`
- **THEN** 响应 MUST 含 `sample_count` 与一致性度量字段，HTTP 200

#### Scenario:无 report 返回 404

- **WHEN** run 存在但无 `report.json`
- **THEN** MUST 返回 HTTP 404
