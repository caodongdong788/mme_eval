# Proposal: 被测 bot 全链路 Langfuse 追踪（bot-only · 原生 SDK）

## Why

现有观测层只有可选 OpenTelemetry（`medeval/observability/tracing.py`），spans 落到 OTLP 后只是普通 span，缺少 LLM 维度的结构化信息（input/output/model/token/cost），不便于复盘被测 bot 的实际对话表现。需要把**被测 bot 的多轮对话**接入 Langfuse，让每次 bot 调用成为结构化 generation，按「run → 会话 → turn」三级嵌套，便于追踪与回放。

本期范围明确为 **bot-only**：只追踪被测 chatbot（`adapter.chat`），judge 的 LLM 调用**不纳入**。

## What Changes

- 新增可选 Langfuse 追踪能力，默认关闭、软依赖、no-op 兜底：未安装 `langfuse` 或 `observability.langfuse.enabled=false` 时，追踪调用 MUST 为零开销空操作，SHALL NOT 抛导入错误或影响主链路。
- 启用时，被测 bot 的每个 user turn 的 `adapter.chat` 调用 MUST 产生一个 Langfuse generation，携带 input（messages）、output（reply）、model、token usage、latency；每条 case/run MUST 包一个会话级 span，并嵌在 run 级 root trace（以 `run_name` 命名）下。
- 追踪 MUST NOT 改变任何判分结果、评分口径或控制流；异常 MUST 静默吞掉。
- judge 链路（`LLMBackend.chat_json`）本期 MUST NOT 被追踪。
- 短命 CLI 进程收尾 MUST flush，保证 trace 不丢。

## Impact

- Affected specs: `observability`（新增「被测 bot 全链路 Langfuse 追踪」能力）。
- Affected code:
  - `pyproject.toml`：新增可选 extra `langfuse`。
  - `medeval/config.py`：新增 `LangfuseCfg` 挂到 `ObservabilityCfg.langfuse`（密钥仅从环境变量读，不落配置快照）。
  - `config.yaml`：补 `observability.langfuse` 默认关闭段。
  - `medeval/observability/langfuse_tracing.py`（新增）：`configure_langfuse` / `conversation` / `generation` / `update_generation` / `flush` / `shutdown`，与 `tracing.py` 同构。
  - `medeval/runner/executor.py`：`_run_one` 透传 `run_idx`，turn 循环外包会话 span，`adapter.chat` 处建并回填 generation。
  - `medeval/service.py`：`evaluate` 调 `configure_langfuse` 并在 finally flush；`run_traces` 的 `phase.run` 处开仅覆盖 bot 阶段的 root trace。
- 判分内核判分逻辑零改动；不触碰 `hard_gate.py` / `TestCase` / `BaseJudge` / `FailureTag`。

## 已知限制

- Ray executor 跨进程不传播 Langfuse/OTel context，bot 追踪在 `run.executor=ray` 下降级（每 worker 独立或关闭）；本地 asyncio executor 完整可用。
