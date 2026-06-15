# Proposal: 修复附加列漂移导致的查询 500

## Why

平台启动 `init_db` 用 `_ensure_additive_columns` 给旧库补列，但此前靠**手工维护**的
`_ADDITIVE_COLUMNS` 字典登记每个新列。多个 ORM 列（`eval_run.token_summary`、
`case_result.cost` / `total_tokens`）历史上加进了模型却漏登记，旧 SQLite 库缺这些列。任何加载
`EvalRun` 的查询（如新接入的 review-queue）会触发 `sqlite3.OperationalError: no such column`，
返回 500。补成可空列后又因旧行 JSON 值为 NULL、而响应模型要求 dict，触发 `ResponseValidationError` 500。

属紧急止血修复（先恢复平台可用），事后按流程补本 change 与测试。

## What Changes

- 迁移改为**由 ORM 元数据驱动**：diff `Base.metadata` 列与库列，自动 `ALTER TABLE ADD COLUMN`
  补齐「可空或带默认」的缺失列；NOT NULL 且无默认的列跳过（留给完整迁移）。新增 ORM 列无需再
  手工登记，杜绝此类漂移。
- JSON 列以空 JSON（`{}` / 默认 list 的列用 `[]`）作默认值追加，并对非空 JSON 列**回填存量 NULL**，
  自愈历史上以 NULL 形式补过的列，消除响应校验 500。
- 删除手工维护的 `_ADDITIVE_COLUMNS` 字典。

## Impact

- Affected specs: `eval-platform-service`（数据库演进/迁移健壮性）。
- Affected code: `server/db.py`（`_ensure_additive_columns` + 新增 `_column_add_ddl` /
  `_json_empty_literal`）；测试 `tests/server/test_review_queue.py`。
- 行为兼容：全新库仍由 `create_all` 建全列，迁移为空操作；旧库自动补齐并自愈 NULL JSON。
