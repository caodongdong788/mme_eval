## MODIFIED Requirements

### Requirement: 平台后端分层

Run 重判 / 试判的 HTTP 校验与派生 run 编排 MUST 位于 `server/services/rejudge_launch.py`（或等价 service）；`routers/runs/rejudge.py` MUST 仅负责 HTTP 绑定与异常映射。
已从 ORM 移除的数据库列（含 `case_result.review_requested`）MUST 由 `db._drop_obsolete_columns` 幂等清理，避免落库 `NotNullViolation`。

#### Scenario: 重判端点行为不变

- **WHEN** 客户端 `POST /api/runs/{id}/rejudge` 携带合法 payload
- **THEN** HTTP 状态码、响应 JSON 与下沉前一致

#### Scenario: 遗留 review_requested 列被清理

- **WHEN** 旧库 `case_result` 仍含 `review_requested NOT NULL` 列且 ORM 已无该字段
- **THEN** `init_db` MUST DROP 该列，新评测落库不得因该列失败

## MODIFIED Requirements

### Requirement: 前端 API 模块

前端 HTTP 客户端 MUST 从 `frontend/src/api/` 子模块导入；根目录 `api.ts` 兼容 shim MUST NOT 存在。

#### Scenario: 构建通过

- **WHEN** 维护者执行 `npm run build`
- **THEN** 所有 import 解析至 `api/index` 或 `api/*` 子模块且无 `src/api.ts`
