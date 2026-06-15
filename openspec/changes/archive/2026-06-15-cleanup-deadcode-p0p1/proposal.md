# Proposal: 清理 P0/P1 死代码与文档不一致

## Why

分层重构后遗留零引用 shim（`runs/_helpers.py`）、前端未使用 API 符号，以及 README/OpenSpec 仍描述已删除的 `_helpers` re-export。

## What Changes

- 删除 `server/routers/runs/_helpers.py`（逻辑已在 `services/`）
- 前端删除 `LONG_TIMEOUT_MS`、`judgeLabel`、`resetJudgeVerdictLabelCacheForTests`；`runLabel` 改为文件内函数
- 更新 `server/README.md` 与 `openspec/specs/eval-platform-service/spec.md` 去除 `_helpers` shim 描述
- 收尾 `graphify update .`

## Non-Goals

- 不删 `GET /api/cases`、不删 `api.requestReview` / `api.getJudgeDefaults`（产品未决）
- 不做 DRY 重构（YAML 打开、标签缓存 hook）
