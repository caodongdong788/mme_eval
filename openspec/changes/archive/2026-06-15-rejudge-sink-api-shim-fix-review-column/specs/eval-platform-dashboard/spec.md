## MODIFIED Requirements

### Requirement: 前端 API 模块

前端 HTTP 客户端与类型 MUST 从 `frontend/src/api/` 子模块导入（`api/index`、`api/types`、`api/*`）；根目录 `api.ts` 兼容 shim MUST NOT 存在。

#### Scenario: 构建通过

- **WHEN** 维护者执行 `npm run build`
- **THEN** 所有 import 解析至 `api/index` 或 `api/*` 子模块且无 `src/api.ts`
