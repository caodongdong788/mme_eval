# Proposal: 用例级 Langfuse 链路 + 平台用例明细可追踪（默认开启 · 自托管）

## Why

上一变更（`add-langfuse-bot-tracing`）把被测 bot 接入了 Langfuse，但：

1. 追踪默认关闭，且整个 run 是一条大 trace，无法从平台直接跳到「某条用例」的链路；
2. 用户希望在平台「用例明细」里，每条用例都能一键打开它在自托管 Langfuse 的完整流程追踪。

因此调整追踪拓扑并打通到前端：**每条用例（case/run）一条独立 Langfuse trace、按 `session = run_name` 分组**（整个 run 在 Langfuse 的 Sessions 视图可整体回放），并把每条用例的 trace 深链落进报告、经后端 API 暴露、在前端「用例明细」按条展示。默认开启，自托管地址与凭据走环境变量；未配置时自动 no-op 且前端隐藏入口（绝不报错）。

## What Changes

- 追踪拓扑 MODIFIED：会话 span 不再挂在 run 级 root trace 下，而是**每条 case/run 成为独立 trace**，trace 的 `session_id` MUST 设为 `run_name`（使同一 run 的所有用例在 Langfuse 归入同一 session）。turn 级 generation 仍为该 trace 的子观测。
- 每条用例 MUST 捕获其 Langfuse trace 深链（`get_current_trace_id` + `get_trace_url`，自动带 project_id、用自托管 `base_url` 拼链；追踪关闭/未配置时为 `None`），落到 `ConversationTrace.langfuse_trace_url`，随代表 trace 进入报告。
- 默认开启：`config.yaml` 的 `observability.langfuse.enabled` MUST 默认 `true`；host/凭据走环境变量；未配置或未装 SDK 时 MUST 自动退化为 no-op，链路 URL 为 `None`。
- 平台后端：用例明细 API MUST 暴露每条用例的 `langfuse_trace_url`。
- 平台前端：「用例明细」每条用例 MUST 提供「追踪链路」入口（新标签页打开该用例的 Langfuse trace）；URL 为空时 MUST 隐藏入口。
- 追踪 MUST NOT 改变任何判分结果、评分口径或控制流；内部异常静默吞掉。judge 调用仍不追踪。

## Impact

- Affected specs: `observability`（MODIFIED 追踪拓扑 + 用例级深链），`eval-platform-dashboard`（ADDED 用例明细追踪入口）。
- Affected code:
  - `medeval/observability/langfuse_tracing.py`：`conversation` 支持 `session_id`、新增 `current_trace_id()` / `trace_url()`。
  - `medeval/models.py`：`ConversationTrace` 新增 `langfuse_trace_url: str | None`。
  - `medeval/runner/executor.py`：`_run_one` 透传 `run_name`，会话 span 设 session 并捕获每条用例 trace_url。
  - `medeval/runner/executor.py::run_cases` 与 `medeval/service.py::run_traces`：透传 `run_name`；`evaluate` 去掉 run 级 root span。
  - `config.yaml`：`observability.langfuse.enabled: true`；`.env.example`：补 `LANGFUSE_*`。
  - `server/`：用例明细 schema/响应暴露 `langfuse_trace_url`。
  - `frontend/`：用例明细每条用例「追踪链路」入口 + `api.ts` 类型。
- 不触碰 `hard_gate.py` / `TestCase` / `BaseJudge` / `FailureTag`。

## 已知限制

- Ray executor 跨进程不传播追踪 context，trace 在 `run.executor=ray` 下降级；本地 asyncio executor 完整可用。
- N-runs（repeat>1）时代表用例的 trace 深链指向被选中的那次 run 的 trace。
