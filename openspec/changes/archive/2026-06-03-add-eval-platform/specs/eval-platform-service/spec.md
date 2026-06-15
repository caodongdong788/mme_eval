## ADDED Requirements

### Requirement: 评测结果持久化

系统 SHALL 将每次评测的 `RunReport` 持久化到关系数据库：run 级汇总与可聚合维度存为 `eval_run` / `case_result` 的标量列，单条用例完整明细（对话、verdict、扣分原因、命中关键词、得分点）存为 JSON 列。数据库连接 MUST 经 `DATABASE_URL` 配置化，默认 SQLite，可切换 PostgreSQL。

#### Scenario: 评测完成后落库

- **WHEN** 一次评测执行完成并产出 `RunReport`
- **THEN** 系统在 `eval_run` 写入一行汇总（total/passed/pass_rate/hard_gate_failed/grading 等），并在 `case_result` 为每条用例写入标量列与 `detail_json`
- **AND** 既写数据库、也按现有规则写 `outputs/<slug>/report.json`（双写兼容）

#### Scenario: 读回与落库一致

- **WHEN** 从数据库读回某次 run 的用例明细
- **THEN** 其内容 MUST 与原始 `CaseResult` 一致（通过率轴 `release_passed/gate_passed/hard_gate_passed`、分数、稳定性、verdict 均无损还原）

### Requirement: benchmark 库管理

系统 SHALL 提供 benchmark 库：支持上传与 `cases/` 同格式的 YAML 用例集，上传时 MUST 用现有 `loader` 校验，校验失败 MUST 拒绝并返回错误；合法 benchmark 保存元数据（name/version/case_count/source）供重复选用。内置 `cases/breast_cancer` MUST 作为 `source=builtin` 的 benchmark 可见。

#### Scenario: 上传合法 benchmark

- **WHEN** 用户上传一个合法的用例 YAML 文件
- **THEN** 系统校验通过后保存用例与元数据，并在 benchmark 列表中可见、可在发起评测时选用

#### Scenario: 上传非法 benchmark 被拒绝

- **WHEN** 用户上传的 YAML 不符合 `TestCase` schema
- **THEN** 系统 MUST 拒绝保存并返回可读的校验错误信息

### Requirement: 评测任务调度与状态跟踪

系统 SHALL 通过 `JobRunner` 抽象异步执行评测：发起后立即创建 `eval_run(status=pending)` 并返回 run id，后台执行时状态流转 `pending → running → success/failed`，失败 MUST 记录 `error_msg`。多个评测任务并发执行 MUST 受并发上限约束。运行进度 SHALL 可被查询。

#### Scenario: 发起评测立即返回并后台执行

- **WHEN** 用户通过 API 发起评测
- **THEN** 系统立即返回 run id（status=pending/running），评测在后台异步执行，不阻塞请求

#### Scenario: 评测失败记录原因

- **WHEN** 后台评测执行过程中抛出异常
- **THEN** 对应 `eval_run.status` MUST 置为 `failed` 且 `error_msg` 记录失败原因

#### Scenario: 查询运行进度

- **WHEN** 评测处于 running 状态时查询其进度
- **THEN** 系统返回当前阶段与已完成用例数等进度信息

### Requirement: 发起评测可配置评测打分模型

系统 SHALL 允许在发起评测时配置评测打分模型（LLM-as-Judge 与 scoring_point 的 provider / model / base_url / api_key），这些参数 MUST 合并进评测配置后再装配 judge；判分逻辑本身 MUST 不被修改。被测 bot 默认沿用服务器 `config.yaml` 的 adapter，并允许可选覆盖。api_key 等敏感参数 MUST NOT 以明文持久化入库。

#### Scenario: 指定打分模型发起评测

- **WHEN** 用户发起评测并指定 judge 的 model 与 base_url
- **THEN** 系统用该打分模型装配 judge 执行评测，`eval_run.judge_overrides` 记录非敏感参数，api_key 不入库

### Requirement: 评测平台 REST API

系统 SHALL 暴露 REST API 覆盖：benchmark 的上传/列表/详情/用例清单/删除；评测的发起/列表/详情/进度/用例结果列表（支持按维度筛选）/单条用例明细/两次 run 对比；以及跨 run 趋势数据与用例库浏览。

#### Scenario: 下钻单条用例明细

- **WHEN** 客户端请求某次 run 中某 `sample_id` 的明细
- **THEN** 系统返回该用例完整对话流水、各 judge verdict、扣分原因、命中关键词、per-run 稳定性与得分点

#### Scenario: 两次 run 对比

- **WHEN** 客户端请求将某次 run 与另一历史 run 对比
- **THEN** 系统返回两者在通过率、各维度与判分指纹上的差异
