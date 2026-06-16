## MODIFIED Requirements

### Requirement: 运行列表分页

`GET /api/runs` SHALL 支持分页参数 `limit`（默认 50，最大 100）与 `offset`。`GET /api/benchmarks`、`GET /api/judge-models`、`GET /api/compare/pairwise` 与 `GET /api/runs/{run_id}/cases` SHALL 采用相同默认与上限。未显式传 `limit` 时 MUST 应用默认 50。

#### Scenario: 默认请求受默认上限约束

- **WHEN** 不带 `limit` 请求运行列表且库内记录超过 50 条
- **THEN** 系统 MUST 最多返回 50 条

#### Scenario: 带分页参数请求

- **WHEN** 带 `limit`/`offset` 请求运行列表
- **THEN** 系统返回对应分页切片，且 `limit` 超过 100 MUST 被拒绝

### Requirement: 用例列表附带人审摘要

`GET /api/runs/{run_id}/cases` 返回的每条用例 SHALL 附带 `review` 字段：若该用例存在人工裁定，则返回摘要；否则为 `null`。列表查询 MUST 使用列投影排除 `CaseResultRow.detail_json` 大字段；依赖 `detail_json` 的派生展示字段（`n_turns`、`langfuse_trace_url`、`guideline_matched`/`guideline_total`）在列表路径 MAY 为占位或 `null`，完整值 MUST 在用例明细或需按 `turns` 过滤时加载 `detail_json` 后计算。

#### Scenario: 列表不加载 detail_json

- **WHEN** 用户请求某 run 的用例列表且未带 `turns` 过滤
- **THEN** 响应 MUST NOT 依赖读取 `detail_json` 全量，`langfuse_trace_url` 与指南命中计数 MAY 为 `null`

#### Scenario: turns 过滤加载明细

- **WHEN** 用户带 `turns=single|multi` 请求用例列表
- **THEN** 系统 MUST 加载 `detail_json` 以正确过滤并返回准确的 `n_turns`

### Requirement: 评测任务调度与状态跟踪

系统 SHALL 通过 `JobRunner` 抽象异步执行评测：发起后立即创建 `eval_run(status=pending)` 并返回 run id，后台执行时状态流转 `pending → running → success/failed`，失败 MUST 记录用户可读的 `error_msg`（完整异常仅进服务端日志）。多个评测任务并发执行 MUST 受并发上限约束。运行进度 SHALL 可被查询，且其完成百分比 MUST 为「跨全部阶段的全局累计值」、随评测推进**单调不回退**（一次评测含多个顺序阶段时，切换阶段 MUST NOT 使百分比下降）。

#### Scenario: 评测失败记录原因

- **WHEN** 后台执行过程中评测或 Pairwise 对比抛出未捕获异常
- **THEN** 对应记录的 `status` MUST 置为 `failed` 且 `error_msg` MUST 为固定用户可读短句，MUST NOT 包含 Python 堆栈或内部异常原文
