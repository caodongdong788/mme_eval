# eval-platform-service Specification (delta)

## MODIFIED Requirements

### Requirement: 改 case 判据派生新 benchmark

系统 SHALL 提供两种派生方式，均**复制源 benchmark 全部用例、按 `sample_id` 只覆盖判据字段**
（`expected_behavior` / `hard_gates` / `rubric` / `scoring_points`，其余字段如 `turns` 不动），
逐条经 `TestCase` schema 校验（非法 MUST 拒绝并返回错误），通过后**另存为一个新的 uploaded
benchmark**，并 MUST 记录 `created_by` 为当前登录用户。该操作 MUST NOT 修改源 benchmark（含内置集）。

- 结构化：`POST /api/benchmarks/{benchmark_id}/derive`（`case_overrides` 列表）；
- YAML：`POST /api/benchmarks/{benchmark_id}/derive-yaml`（`yaml_text` 整段用例 YAML）。

派生时若覆盖项的 `sample_id` 在源 benchmark 中**不存在 MUST 跳过丢弃**（不新增、不报错）；
若**没有任何 `sample_id` 命中** MUST 拒绝并返回可读错误。该派生本身 MUST NOT 触发重判。

#### Scenario: 派生不影响源 benchmark

- **WHEN** 用户基于某 benchmark 改若干用例判据并派生
- **THEN** 系统创建一个含改后判据的新 benchmark，源 benchmark 的用例 MUST 保持原样

#### Scenario: 未匹配 sample_id 丢弃、零匹配报错

- **WHEN** 提交的 YAML 含源集中不存在的 `sample_id`
- **THEN** 这些条目 MUST 被丢弃；若一条都没匹配上，系统 MUST 拒绝派生并返回可读错误

#### Scenario: 仅判据字段生效

- **WHEN** 用户在 YAML 里同时改了某用例的 `turns` 与 `hard_gates`
- **THEN** 新 benchmark MUST 只采用改后的 `hard_gates`，`turns` 保持源用例原样

#### Scenario: 非法判据被拒绝

- **WHEN** 派生请求中某条用例覆盖不符合 `TestCase` schema
- **THEN** 系统 MUST 拒绝派生并返回可读的校验错误

## ADDED Requirements

### Requirement: 导出过滤用例的完整 YAML 供在线编辑

系统 SHALL 提供 `GET /api/runs/{run_id}/cases-yaml`，接收与 `GET /api/runs/{run_id}/cases`
相同的过滤参数（level / release_passed / stability / scenario / tag），返回该 run 命中用例在其
benchmark 中的**完整用例 YAML 文本**（可被 `load_cases` 解析），供前端预填判据编辑器。run 无关联
benchmark 或过滤后无用例时 MUST 返回 400。

#### Scenario: 按过滤导出可解析 YAML

- **WHEN** 用户带过滤参数请求某 run 的 cases-yaml
- **THEN** 返回的 YAML MUST 仅含命中用例的完整定义，且可被 `load_cases` 解析校验
