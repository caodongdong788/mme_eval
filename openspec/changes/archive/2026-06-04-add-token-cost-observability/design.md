## Context

延迟管线（change `add-latency-metrics` 起）已经跑通一条"仅观测"的标准链路：

```
adapter → ConversationTrace.turn_latencies_ms / duration_ms
        → voting.fold_n_runs → CaseResult.per_run_latency_ms
        → aggregator._latency_summary → RunReport.latency_summary
        → markdown_report._latency_section / diff._latency_diff
        → server ingest（run.latency_summary / case.latency_ms）
        → frontend「性能（延迟）」Card
```

本期 token/cost **逐点对仗照搬**，不发明新机制。唯一与延迟不同的两处：
1. **数据来源已存在但会被裁剪**：usage 在 `ChatResponse.raw["usage"]`，但 `store_raw=on_error` 默认在成功轮次清空 `raw_responses`。因此必须像 `turn_latencies_ms` 一样在 `_run_one` 里**当场抽取**成 trace 独立字段，而非事后从 raw 读。
2. **cost 需要外部单价**：usage 只给 token 数，成本 = token × 单价，单价从 `config.yaml` 新增 `cost` 段读取，随 `config_snapshot` 落盘以便 diff 区分"用量变化"vs"单价调整"。

## Goals / Non-Goals

**Goals**
- 逐轮 / 逐 run / run 级三级 token 字段，对仗延迟三级字段。
- 配置单价时折算 cost；未配置时只出 token、cost 标 N/A。
- 报告、diff、平台看板各加一栏，文案统一"仅观测、不计分、不否决"。

**Non-Goals**
- 不让 token/cost 参与任何评分、阈值、否决（与延迟同等"只观测"地位）。
- 不做 `http` adapter 的 usage 解析（MVP 只认 openai_compat 形状）。
- 不做按模型分别计价（单一全局单价；judge 模型的 token 暂不纳入 bot 成本）。
- 不做历史 DB 数据回填。

## Decisions

### D1. trace 字段形状：`turn_token_usage: list[dict]`
逐轮存 `{"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}`，对仗 `turn_latencies_ms: list[float]`。认不出 usage 的轮次 append `{}`（占位，聚合时跳过空 dict），保证与轮次对齐且历史兼容（`default_factory=list`）。

### D2. 归一化器 `_extract_token_usage(raw) -> dict`
放在 `runner/executor.py`（或 `runner/` 小工具），只认 OpenAI 形状键 `prompt_tokens/completion_tokens/total_tokens`（兼容 `usage` 嵌套）。缺 `total_tokens` 时回退为 `prompt+completion`。认不出返回 `{}`。在 `turn_latencies_ms.append(...)` 同一处调用，**在任何 trim 之前**完成。

### D3. CaseResult：`per_run_tokens: list[int]`
逐 run 的会话总 token（对仗 `per_run_latency_ms`）。在 `voting.fold_n_runs` 里从 `trace.turn_token_usage` 求和折叠（N=1 与 N>1 两条分支都补，紧贴现有 `per_run_latency_ms` 赋值行）。

### D4. RunReport：`token_summary: dict`
`aggregator._token_summary(results, pricing)`：过滤 `trace.error` 非空的 run（与延迟同口径），产出
```python
{
  "count": int,                      # 计入统计的 run 数
  "total_prompt_tokens": int,
  "total_completion_tokens": int,
  "total_tokens": int,
  "avg_tokens_per_run": float,
  # 配置单价时附加：
  "cost": float, "currency": str,
  "cost_per_run": float,
}
```
无任何 token 数据 → 返回 `{}`（报告段显示 N/A，对仗 `_latency_summary`）。

### D5. cost 单价：`config.yaml` 顶层 `cost` 段
```yaml
cost:
  currency: "USD"
  input_per_million: 0.0   # 每百万 prompt token 单价
  output_per_million: 0.0  # 每百万 completion token 单价
```
`config.py` 加 `CostConfig`（全 0 默认 = 未配置 → 不出 cost）。pricing 经 `build_report` 现有 `config_snapshot` 通道传入 `_token_summary`（`config_snapshot["cost"]`），无需改 `build_report` 签名以外的链路。`input/output` 均为 0 时视为"未配置单价"，只出 token。

### D6. 平台落库
- `models_db.RunRow` 加 `token_summary: JSON default=dict`；`CaseRow` 加 `total_tokens: Float nullable` + `cost: Float nullable`。
- `schemas.py` 对应加字段；`ingest.py` 从 `report.token_summary` 与 `cr.per_run_tokens`（求和）/ case cost 落库。
- SQLite 新列靠 `default`/`nullable` 兼容老库；如启用 Postgres 需建表时即含新列（首次建表无碍）。

### D7. 前端
`api.ts` 的 `RunReport` 接口加 `token_summary: Record<string, any>`。`RunDashboardPage.tsx` 复制「性能（延迟）」Card → 「成本 / Token（仅观测）」Card：展示 总 token / 平均每 run token / cost（有则显示，无则 token-only）；无数据显示"本次评测无 token 数据"。

## Risks / Trade-offs

- **usage 形状漂移**：不同 OpenAI 兼容厂商 usage 键可能略有差异 → 归一化器只认标准三键、认不出留空并跳过，绝不抛错（观测降级而非中断评测）。
- **judge 成本未计入**：MVP 只统计被测 bot 的 token，不含 LLM-judge 的开销 → 在报告文案注明"仅被测 bot"。
- **DB 迁移**：新增列。SQLite 默认值兼容；若已有 Postgres 部署需 DDL，归档前在 tasks 标注。

## Migration Plan

纯加法、字段默认值兜底，无数据回填。历史 run / report.json 读出时 token 字段为空 → 报告与看板显示 N/A。

## Open Questions

- 是否后续把 judge 模型 token 也纳入"评测总成本"另起一段？（本期 Non-Goal）
- 是否需要按模型分别计价表？（本期单一全局单价）
