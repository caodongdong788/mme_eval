## MODIFIED Requirements

### Requirement: 人工审核队列

系统 SHALL 提供按 run 的人工审核队列。某 run 的用例 MUST 入队当且仅当满足任一：
(a) `case_result.needs_human_review = true`；(b) `release_passed = false`（任何上线判定失败的用例，
原因记 `release_failed`）；(c) 该用例为红旗题（`hard_gates.red_flag_triage != none`）且
`release_passed = false`（在 release_failed 之上额外标注更具体的 `red_flag_failed`）。
`GET /api/runs/{run_id}/review-queue` SHALL 接收与 `/cases` 相同的过滤参数，返回入队用例及其入队
原因、机器判分要点、是否已审与已有标注。

#### Scenario: 上线失败一律入队

- **WHEN** 一个用例 `release_passed=false`（无论是否红旗、是否 needs_human_review）
- **THEN** 该用例 MUST 出现在 review-queue，且入队原因 MUST 含 `release_failed`

#### Scenario: 通过用例不入队

- **WHEN** 一个用例 `release_passed=true` 且非 needs_human_review
- **THEN** 该用例 MUST NOT 入队
