# Proposal: Server Layering P1（五域 service 化）

## Why

P0 迁出 `runs/_helpers` 后，`judge_models` / `pairwise` / `review` / `config` / `dashboard` 路由仍直连 ORM 并内联业务。P1 MUST 为每域建立 `server/services/*` 模块，router 仅做 HTTP 绑定。

## What Changes

- `services/judge_models.py` — 判分模型 CRUD
- `services/dashboard.py` — 趋势聚合
- `services/platform_config.py` — failure-tags / judge-labels / judge-defaults / release-thresholds
- `services/review.py` — HITL 队列/统计/annotate
- `services/pairwise.py` — Pairwise HTTP 侧 CRUD + 校准
- `ReleaseThreshold*` / `ProfileCoverage` schema 迁入 `schemas.py`
- 对应 router 瘦身为薄控制层

## Non-Goals

- 不引入 `repositories/`
- 不迁移 `benchmarks` router / `runs/crud` 创建逻辑（P2）
- 不改 REST 路径与 JSON 字段
