# Proposal: Server Layering P0（迁出 runs/_helpers）

## Why

分层审计指出 `server/routers/runs/_helpers.py`（~250 行）实质为业务服务层，却位于 router 包内，导致 Router→DB 直连与职责混淆。P0 MUST 将其迁至 `server/services/` 而不改变任何 HTTP 行为。

## What Changes

- 新增 `server/services/runs.py`：`get_run_or_404`、`source_out_dir`、`create_derived_run`
- 新增 `server/services/case_query.py`：用例查询/审核附加字段/HITL 队列辅助等
- `routers/runs/_helpers.py` 改为薄 re-export（向后兼容）
- `routers/runs/{crud,cases,rejudge,review}.py` 改为从 `services` 导入
- 新增 `tests/server/test_case_query_service.py` 覆盖纯函数

## Non-Goals（P0）

- 不引入 `repositories/` 层
- 不迁移 `judge_models` / `pairwise` / `config` 等其它 router 内联逻辑（P1）
- 不改 REST 路径、响应 schema、SQL 语义

## Risks

- import 路径变更可能影响未发现的 monkeypatch → `_helpers` 保留 re-export
