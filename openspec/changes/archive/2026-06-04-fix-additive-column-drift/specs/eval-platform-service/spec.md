# eval-platform-service Specification (delta)

## ADDED Requirements

### Requirement: 数据库附加列幂等迁移由 ORM 元数据驱动

系统 SHALL 在启动建表后，由 ORM 元数据（`Base.metadata`）驱动幂等补齐旧库缺失的列：对每张已存在
的表，凡 ORM 中存在而库中缺失、且「可空或带默认值」的列 MUST 以可空形式 `ALTER TABLE ADD COLUMN`
追加；NOT NULL 且无默认的列 MUST 跳过（留待完整迁移）。新增 ORM 列 MUST NOT 依赖任何手工维护的
列登记表。JSON 列 MUST 以合法空 JSON（对象 `{}`，默认 list 的列用 `[]`）作为追加默认值，且系统
MUST 把非空 JSON 列中存量为 NULL 的值回填为空 JSON，避免响应模型校验失败。

#### Scenario: 旧库缺列自动补齐

- **WHEN** 旧库的某表缺少 ORM 中新增的可空/带默认列
- **THEN** 启动迁移 MUST 自动补齐该列且可重复执行（幂等），后续查询 MUST NOT 因缺列报错

#### Scenario: 非空 JSON 列的 NULL 自愈

- **WHEN** 某非空 JSON 列在旧库中存在为 NULL 的存量行
- **THEN** 迁移 MUST 将其回填为合法空 JSON，使读取该行的响应 MUST NOT 因 JSON 为空而 500
