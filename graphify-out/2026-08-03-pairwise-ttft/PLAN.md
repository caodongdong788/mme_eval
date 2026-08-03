# Pairwise TTFT 可观测性计划

## 目标

在 CX Agent 的 SSE 流式响应中，以请求发出到首个非空 `text_delta` 到达的时间作为
TTFT（Time To First Token），贯通评测 trace、报告聚合、平台落库和 Pairwise 展示。
TTFT 仅用于观测，不影响 Pairwise 胜负或任何质量评分。

## 口径

- 单轮 TTFT：本次 HTTP 请求开始到首个非空 `text_delta` 事件到达。
- 发生客户端重试时：最终成功请求的 TTFT 加上此前失败尝试和退避耗时，反映用户实际等待。
- 多轮会话：以该次会话所有成功轮次 TTFT 的平均值作为 Case 级 TTFT。
- Run 聚合：对有效 Case/重复运行的 Case 级 TTFT 计算 count、平均、中位、P90、最大值。
- 历史数据没有 SSE 到达时间，保持为空并在前端显示 N/A，不用端到端耗时估算。

## 实施

1. 将 `CxAgentAdapter` 从缓冲整段响应改为逐行消费 SSE，并记录首个非空文本增量时间。
2. 增加 `turn_ttft_ms`、`per_run_ttft_ms`、`ttft_summary`，沿现有延迟管线聚合。
3. 为 `eval_run.ttft_summary` 和 `case_result.ttft_ms` 增加兼容迁移与落库。
4. Pairwise 全量与 RAG 子集观测均返回 TTFT 汇总。
5. 前端将“平均首 Token 耗时（TTFT）”放在端到端耗时卡片之前。
6. 覆盖 SSE 时序、聚合、迁移、API 与前端构建测试。
