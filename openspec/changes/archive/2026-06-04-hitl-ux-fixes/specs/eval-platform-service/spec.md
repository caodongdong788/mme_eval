# eval-platform-service Specification (delta)

## MODIFIED Requirements

### Requirement: 人工审核队列

系统 SHALL 提供按 run 的人工审核队列。某 run 的用例 MUST 入队当且仅当满足任一：
(a) `case_result.needs_human_review = true`；(b) `release_passed = false`（任何上线判定失败的用例，
原因记 `release_failed`）；(c) 该用例为红旗题（`hard_gates.red_flag_triage != none`）且
`release_passed = false`（在 release_failed 之上额外标注更具体的 `red_flag_failed`）；
(d) 被手动加入（`case_result.review_requested = true`）。
`GET /api/runs/{run_id}/review-queue` SHALL 接收与 `/cases` 相同的过滤参数，返回入队用例及其入队
原因、机器判分要点、是否已审与已有标注。`POST /api/runs/{run_id}/cases/{sample_id}/request-review`
SHALL 把该用例置为手动入队（幂等）。

#### Scenario: 上线失败一律入队

- **WHEN** 一个用例 `release_passed=false`（无论是否红旗、是否 needs_human_review）
- **THEN** 该用例 MUST 出现在 review-queue，且入队原因 MUST 含 `release_failed`

#### Scenario: 通过用例不入队

- **WHEN** 一个用例 `release_passed=true` 且非 needs_human_review、未手动加入
- **THEN** 该用例 MUST NOT 入队

#### Scenario: 手动加入队列

- **WHEN** 用户对某用例调用 request-review
- **THEN** 该用例 MUST 进入队列，重复调用 MUST 幂等且不报错

## ADDED Requirements

### Requirement: 失败标签中文标签元数据接口

系统 SHALL 提供 `GET /api/config/failure-tags`，返回 `FailureTag` 受控词表的 `{枚举值: 中文短标签}`
映射（取自 `FailureTag.label_zh`，单一信任源）。该接口 MUST NOT 重复定义标签文案，前端遇未知值
MUST 回退展示原始枚举值。

#### Scenario: 返回中文标签映射

- **WHEN** 前端请求 failure-tags 元数据
- **THEN** 响应 MUST 为非空映射，且 `missed_red_flag` MUST 映射为其 `label_zh`（如「漏报红旗」）
