# Proposal: Server Layering P2（benchmark / run CRUD / case export）

## Why

P1 后 `routers/benchmarks.py`、`runs/crud.py`、`runs/cases.py` 仍内联 ORM/SQL 与编排逻辑。P2 MUST 迁入 `server/services/`。

## What Changes

- `services/benchmark_catalog.py` — benchmark 列表/元数据/删除/上传上限/用例 brief
- 扩展 `services/runs.py` — create/list/delete/rename/pin/diff
- `services/case_export.py` — cases-yaml、飞书导出、用例 detail
- 对应 router 瘦身；`server/benchmarks.py` 保留领域实现（校验/派生）

## Non-Goals

- 不搬迁 `server/benchmarks.py` 本体
- 不改 REST 路径与 JSON
