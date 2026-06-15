# eval-platform-service Specification (delta)

## ADDED Requirements

### Requirement: 用例列表附带人审摘要

`GET /api/runs/{run_id}/cases` 返回的每条用例 SHALL 附带 `review` 字段：若该用例存在人工裁定，
则为最新一条裁定的摘要（`verdict` ∈ {agree, override}、`reviewer`、`suggestion`、`comment`）与
该用例裁定总条数 `count`；无裁定时 MUST 为 null。该摘要为只读旁路，MUST NOT 改动任何判分字段。

#### Scenario: 已裁定用例返回最新结论

- **WHEN** 某用例存在一条或多条人工裁定
- **THEN** 其 `review` MUST 反映最新一条的 verdict 与建议/备注，`count` MUST 等于裁定总条数

#### Scenario: 未裁定用例

- **WHEN** 某用例无任何裁定
- **THEN** 其 `review` MUST 为 null
