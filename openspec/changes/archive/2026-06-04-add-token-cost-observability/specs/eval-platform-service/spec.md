## ADDED Requirements

### Requirement: 平台落库必须包含 token/cost 观测字段

评测结果入库时，run 级记录 MUST 持久化 `RunReport.token_summary`，case 级记录 MUST 持久化该用例的总 token 与（配置单价时的）cost。这些字段 MUST 仅作观测保留，MUST NOT 参与平台侧任何通过/失败判定或排序默认口径。新增数据库列 MUST 对历史库向后兼容（带默认值 / 可空），读取历史无该字段的 run 时 MUST 安全返回空值。

#### Scenario: 入库保留 token_summary

- **WHEN** 一次含 token 数据的评测结果被 ingest
- **THEN** run 行 MUST 含 `token_summary`，对应 case 行 MUST 含总 token（及配置单价时的 cost）

#### Scenario: 历史 run 缺字段安全读取

- **WHEN** 读取一个入库时尚无 token 字段的历史 run
- **THEN** API MUST 返回空的 token 字段，MUST NOT 报错
