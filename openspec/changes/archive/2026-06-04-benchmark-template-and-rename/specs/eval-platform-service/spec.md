# eval-platform-service Specification (delta)

## ADDED Requirements

### Requirement: 修改 benchmark 名称与描述

系统 SHALL 提供 `PATCH /api/benchmarks/{benchmark_id}`，允许修改 benchmark 的 `name` 与
`description`（二者均可选，仅更新提供的字段）。内置（builtin）benchmark MUST NOT 可改，
返回 400。名称若提供则 MUST 非空（去除首尾空白后），空名 MUST 返回 422。benchmark 不存在
MUST 返回 404。此操作 MUST 只改名称/描述，不触碰用例内容与判据。

#### Scenario: 改名与描述

- **WHEN** 用户对一个上传 benchmark 提交新的名称与描述
- **THEN** 系统 MUST 持久化新值并在后续列表/详情返回

#### Scenario: 内置不可改

- **WHEN** 用户尝试 PATCH 内置 benchmark
- **THEN** 系统 MUST 返回 400 且不修改任何字段
