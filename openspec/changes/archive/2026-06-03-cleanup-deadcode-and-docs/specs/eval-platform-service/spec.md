## MODIFIED Requirements

### Requirement: 评测结果持久化

系统 SHALL 将每次评测的 `RunReport` 持久化到关系数据库：run 级汇总与可聚合维度存为 `eval_run` / `case_result` 的标量列，单条用例完整明细（对话、verdict、扣分原因、命中关键词、得分点）存为 JSON 列。数据库连接 MUST 经 `MEDEVAL_DATABASE_URL` 配置化，默认 SQLite，可切换 PostgreSQL。

#### Scenario: 评测完成后落库

- **WHEN** 一次评测执行完成并产出 `RunReport`
- **THEN** 系统在 `eval_run` 写入一行汇总（total/passed/pass_rate/hard_gate_failed/grading 等），并在 `case_result` 为每条用例写入标量列与 `detail_json`
- **AND** 既写数据库、也按现有规则写 `outputs/<slug>/report.json`（双写兼容）

#### Scenario: 读回与落库一致

- **WHEN** 从数据库读回某次 run 的用例明细
- **THEN** 其内容 MUST 与原始 `CaseResult` 一致（通过率轴 `release_passed/gate_passed/hard_gate_passed`、分数、稳定性、verdict 均无损还原）
