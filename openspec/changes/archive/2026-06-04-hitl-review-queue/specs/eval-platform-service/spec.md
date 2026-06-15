# eval-platform-service Specification (delta)

## ADDED Requirements

### Requirement: 人工审核队列

系统 SHALL 提供按 run 的人工审核队列。某 run 的用例 MUST 入队当且仅当满足任一：
(a) `case_result.needs_human_review = true`；(b) 该用例为红旗题（`hard_gates.red_flag_triage != none`）
且 `release_passed = false`；(c) 被手动加入（`case_result.review_requested = true`）。
`GET /api/runs/{run_id}/review-queue` SHALL 接收与 `/cases` 相同的过滤参数，返回入队用例及其入队
原因、机器判分要点、是否已审与已有标注。`POST /api/runs/{run_id}/cases/{sample_id}/request-review`
SHALL 把该用例置为手动入队（幂等）。

#### Scenario: 三类用例入队

- **WHEN** 一个 run 含 `needs_human_review=true` / 红旗且未通过 / 被手动加入 的用例
- **THEN** review-queue MUST 返回这些用例并标注各自入队原因，普通已通过用例 MUST NOT 入队

#### Scenario: 手动加入队列

- **WHEN** 用户对某用例调用 request-review
- **THEN** 该用例 MUST 进入队列，重复调用 MUST 幂等且不报错

### Requirement: 人工裁定记录且不回写判分

系统 SHALL 提供 `POST /api/runs/{run_id}/cases/{sample_id}/annotate`，记录一条裁定
（`verdict` ∈ {`agree`,`override`}、可选 `suggestion`/`comment`），`reviewer` 取当前飞书登录用户
显示名（未登录可空）。同一用例 MUST 允许多条裁定。`verdict` 非法 MUST 返回 422，用例不在该 run
MUST 返回 404。裁定 MUST NOT 修改该用例的任何判分字段（`verdict`/`score`/`release_passed`/
`gate_passed`/`hard_gate_passed`）——人审是独立旁路层。`GET /api/runs/{run_id}/review-stats`
SHALL 返回队列总数、已审/待审数、agree/override 数与人审通过率/分歧率。

#### Scenario: 裁定落库不影响判分

- **WHEN** 用户对某用例提交 agree 或 override 裁定
- **THEN** 系统 MUST 记录该裁定（含 reviewer），且该用例的 `release_passed` 与 `composite_score`
  等判分字段 MUST 保持不变

#### Scenario: 统计口径

- **WHEN** 队列中部分用例已被裁定
- **THEN** review-stats MUST 返回正确的已审/待审计数与 agree/override 占比
