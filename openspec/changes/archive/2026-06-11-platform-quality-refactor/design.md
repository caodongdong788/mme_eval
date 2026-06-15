## Context

平台已上线运行，判分内核与平台共用 `evaluate()` 编排核。本次为「不改行为」的工程加固，最大风险是大面积重构引入回归，因此**分批 + TDD + 每批全量验证**。

## Goals / Non-Goals

- Goals：结构清晰、首屏更小、列表更快、路径更安全、错误可观测、类型更完整。
- Non-Goals：
  - 不引入资源级授权 / 租户隔离（保持「登录后可见全部」现状，用户已确认排除）。
  - 不改判分口径、评分算法、HardGate 启发式、`TestCase`/`BaseJudge`/`FailureTag`。
  - 不引入 Redis（当前单进程，缓存用进程内 LRU + mtime 失效即可；审计中的 Redis 项降级为内存缓存）。
  - 不引入新前端 UI 库（锁定 AntD 单一库）。

## Key Decisions

1. **「行为不变」判定基线**：现有全量 `pytest` + 前端 `tsc/build` + `medeval run --dry-run` 为回归基线；新增测试只覆盖「新增的防御/性能行为」与「原行为保持」。
2. **缓存选型**：benchmark cases 读盘用 `functools.lru_cache` 包一层 + `(path, mtime)` 作键，避免脏读；不引入外部依赖。
3. **分页兼容**：`GET /api/runs` 加可选 `limit/offset`，默认 `limit` 取高上限（如 500），不传则行为等同现状（前端无需改动即兼容）。
4. **路径安全**：新增 `safe_join(root, *parts)` 工具，对所有 `outputs/`、`uploads/` 拼接做 `resolve()` + `is_relative_to(root)` 校验；`run_slug` 增加字符白名单（不改既有合法 slug 的产出）。
5. **SESSION_SECRET**：仅当 `MEDEVAL_ENV=production`（或显式开关）且 secret 仍为默认值时启动失败；开发/测试默认值保持可用，**不破坏现有本地启动**。
6. **前端取数兜底**：新增 `useAsyncData` hook，统一 `{ data, loading, error, reload }`；页面在 `error` 时渲染 `Result/Alert` 而非永久 `Spin`。
7. **公共依赖收口**：后端新增 `server/deps.py` 收敛 `get_*_or_404`、`_creator_name`、`CaseFilterParams`；router 只做 HTTP 映射。

## Risks / Trade-offs

- 拆大页面（F3）触面广 → 放最后，先靠前序批次补足类型与 hook 抽象再拆。
- 加索引对存量 SQLite：走现有 ORM 幂等补列路径，迁移在空表/存量库都需验证。
- 生产 SESSION_SECRET 强校验改变启动行为 → 必须在部署文档同步，默认环境不受影响。

## Migration / Rollout

每批独立可回滚。收尾统一 `openspec validate --strict` → `archive`，并 `graphify update .`。
