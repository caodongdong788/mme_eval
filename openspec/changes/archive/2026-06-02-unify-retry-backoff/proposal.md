## Why

重试 / 超时逻辑散在三处、语义还不一致：

1. `runner/executor.py::_run_one`：每个 user turn 包 `asyncio.wait_for(timeout_s)` + 重试循环（`retry+1` 次），且**对任何失败（含 `resp.error`）立即重试、无退避**。
2. `adapter/openai_compat.py`：把 `timeout_s` 传给 `AsyncOpenAI` 客户端（**它自己又有一层 per-request 超时**），异常一律吞成 `ChatResponse.error`。
3. `judges/llm_backend.py::chat_json`：有**自己的指数退避**（`RateLimitError`，`min(40, 2^n*5+jitter)`）。

后果：被测 bot 路径"无退避、见错就重试"，judge 路径却"智能退避"，两套退避数学各写一份；executor 的 `wait_for(timeout_s)` 与 openai 客户端 `timeout=timeout_s` 同值同时触发，谁先赢是 racy 的。

研发阶段，沿"单一真值源"主线把退避数学收敛成一处，并让 bot 路径也能（按需）退避。

## What Changes

- 新增 `medeval/retry.py`：
  - `backoff_delay(attempt, *, base, factor=2.0, max_delay, jitter=0.0)`——纯函数，单一退避数学源。
  - `retry_async(fn, *, max_retries, retryable, base, factor, max_delay, jitter, on_retry, sleep)`——通用异步指数退避重试（异常驱动）。
- `judges/llm_backend.py::chat_json` 改用 `retry_async`（`retryable=isinstance RateLimitError`，参数 `base=5/factor=2/max_delay=40/jitter=2`），**退避行为逐位不变**（调用次数、退避次数、上限语义一致）。
- `runner/executor.py`：重试之间引入**可配置指数退避**，复用 `backoff_delay`；新增 `RunCfg.retry_backoff_base_s`（默认 `0.0` = 关闭，**保持现有立即重试行为**）与 `retry_backoff_max_s`（默认 `40.0`）。`base<=0` 时完全不 sleep。
- 明确 **executor 为端到端超时单一归属**（`wait_for`），openai 客户端 `timeout` 退为安全网；以注释固化该边界（不改行为）。

## Capabilities

### Modified Capabilities
- `dialog-runner`：新增要求"Runner 重试必须支持可配置指数退避，并与 LLM 后端复用同一退避数学实现（单一真值源）"——禁止两处各写一套退避公式；退避默认关闭以保持既有行为，超时归属单一明确。

## Impact

- 代码：新增 `medeval/retry.py`；`judges/llm_backend.py`、`runner/executor.py`、`runner/__init__`（如需导出）、`config.py`（RunCfg 两个字段）、`service.py`（把 backoff 配置透传给 `run_cases`）；新增 `tests/test_retry.py` + executor 退避测试。
- 行为：默认配置下**完全不变**（`retry_backoff_base_s=0.0` → 无 sleep、立即重试）；LLMBackend 退避逐位不变（现有 `test_llm_backend` 回归绿）。仅当用户显式配置 `retry_backoff_base_s>0` 时，bot 路径重试之间才插入退避。
- 兼容性：`run_cases` 新增 kwargs 带默认值，旧调用零改动；现有 runner 测试（均 `retry=0`）不受影响。
- 依赖：不引入新依赖。
