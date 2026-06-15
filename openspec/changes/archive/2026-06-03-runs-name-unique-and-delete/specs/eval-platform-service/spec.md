## ADDED Requirements

### Requirement: 发起评测名称唯一性

系统 SHALL 在发起评测时校验最终 run 名称（用户填写的 `run_name`，缺省时为 benchmark 名）
的唯一性；若与已存在的 run 重名，系统 MUST 拒绝创建并返回 409 及可读提示，不得创建该 run。

#### Scenario: 重名被拒绝

- **WHEN** 用户以一个已存在 run 同名的名称发起评测
- **THEN** 系统返回 409 并提示名称已存在，不创建新 run

#### Scenario: 唯一名称正常创建

- **WHEN** 用户以未被占用的名称发起评测
- **THEN** 系统正常创建 run 并开始执行

### Requirement: 删除评测 run

系统 SHALL 提供 `DELETE /api/runs/{run_id}`，删除指定 run 及其级联用例结果，并清理其
产物目录；运行中或等待中的 run MUST NOT 被删除（返回 400）。删除不存在的 run 返回 404。

#### Scenario: 删除已完成的 run

- **WHEN** 用户删除一个已完成（成功/失败）的 run
- **THEN** 系统删除该 run 与其用例结果，返回 204，后续查询该 run 返回 404

#### Scenario: 运行中不可删除

- **WHEN** 用户删除一个状态为 running 或 pending 的 run
- **THEN** 系统返回 400 并提示运行中不可删除

#### Scenario: 删除不存在的 run

- **WHEN** 用户删除一个不存在的 run id
- **THEN** 系统返回 404
