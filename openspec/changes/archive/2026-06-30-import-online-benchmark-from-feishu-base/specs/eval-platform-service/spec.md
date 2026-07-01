## MODIFIED Requirements

### Requirement: benchmark 库管理

系统 SHALL 提供 benchmark 库：支持上传与 `cases/` 同格式的 YAML 用例集，上传时 MUST 用现有 `loader` 校验，校验失败 MUST 拒绝并返回错误；合法 benchmark 保存元数据（name/version/case_count/source）供重复选用。内置 `cases/breast_cancer` MUST 作为 `source=builtin` 的 benchmark 可见。

当上传请求的 `source=online` 时，系统 MUST 复用同一个 `POST /api/benchmarks` 入口支持两类输入：JSONL 文件或 `source_url` 飞书 Base URL。若提供 `source_url`，系统 MUST 使用当前登录用户的 `user_access_token` 调用飞书多维表格 OpenAPI 读取记录；若未提供 `source_url`，系统 MUST 沿用线上 JSONL 文件解析。飞书 Base 记录转 benchmark 时 MUST 把每条记录的每轮用户输入与 Cx 输出按顺序写入 `turns`，不得只保留第一轮。

#### Scenario: 上传合法 benchmark

- **WHEN** 用户上传一个合法的用例 YAML 文件
- **THEN** 系统校验通过后保存用例与元数据，并在 benchmark 列表中可见、可在发起评测时选用

#### Scenario: 上传非法 benchmark 被拒绝

- **WHEN** 用户上传的 YAML 不符合 `TestCase` schema
- **THEN** 系统 MUST 拒绝保存并返回可读的校验错误信息

#### Scenario: 从飞书 Base URL 导入线上 benchmark

- **WHEN** 用户提交 `source=online`、benchmark 名称与飞书 Base URL
- **THEN** 系统 MUST 读取 URL 指定的数据表/视图，将每条记录转换为一个 `source=online` case 并保存为 benchmark
- **AND** 每个 case 的 `turns` MUST 按「第一轮用户输入 / 第一轮Cx输出」到「第四轮用户输入 / 第四轮Cx输出」的非空轮次完整落盘

#### Scenario: Base URL 导入权限不足

- **WHEN** 当前用户未登录、token 失效或缺少读取该 Base 的权限
- **THEN** 系统 MUST 拒绝导入并返回可读错误，不得创建空 benchmark
