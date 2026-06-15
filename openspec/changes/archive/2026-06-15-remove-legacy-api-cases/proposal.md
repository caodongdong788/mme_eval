# Proposal: 删除遗留 `GET /api/cases`

## Why

`GET /api/cases` 与 `GET /api/benchmarks` 返回相同的 benchmark 列表；仓库内前端、测试、脚本均无调用，属初始 API 遗留。

## What Changes

- 删除 `server/routers/cases.py`
- `app.py` 取消挂载 `cases.router`
- 更新 `server/README.md` 架构说明

## Non-Goals

- 不改 `GET /api/benchmarks` 与 run 维度 `/api/runs/{id}/cases`
