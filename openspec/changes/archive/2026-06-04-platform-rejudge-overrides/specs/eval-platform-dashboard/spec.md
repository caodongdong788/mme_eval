# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 重判弹框可调判分口径与模型

看板的「重判」入口 SHALL 提供一个弹框，允许用户在重判前临时调整四模块权重/阈值，
并可选填新的 judge 模型（provider/model/base_url/api_key），提交后以这些覆盖发起重判并
跳转到新 run。弹框 MUST 提示这些改动仅作用于本次重判、不改服务器配置。

#### Scenario: 从弹框发起带覆盖的重判

- **WHEN** 用户在重判弹框里改了某模块权重或填了新模型并提交
- **THEN** 前端 MUST 携带这些覆盖调用重判 API，并在新 run 创建后跳转到其看板

### Requirement: 用例详情页可编辑判据并另存重判

用例详情页 SHALL 提供判据编辑器（至少覆盖 `hard_gates` 与 `expected_behavior` 的
must_have / must_not_have），用户编辑后可「另存为新 benchmark 并重判」：前端 MUST 先派生
一个带改后判据的新 benchmark，再以 `cases_benchmark_id` 发起重判并跳转新 run。

#### Scenario: 编辑判据后另存并重判

- **WHEN** 用户在用例详情页改了该用例的 must_have 或硬门槛并点「另存为新 benchmark 并重判」
- **THEN** 前端 MUST 先创建含改动的新 benchmark，再用其发起重判并跳转到新 run 看板

### Requirement: benchmark 列表展示上传人

Benchmark 库列表 SHALL 新增「上传人」列，展示 `created_by`（内置/无则展示占位）。

#### Scenario: 列表显示上传人

- **WHEN** 用户打开 Benchmark 库列表
- **THEN** 每行 MUST 显示该 benchmark 的上传人（或内置/未知占位）
