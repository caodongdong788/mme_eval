## ADDED Requirements

### Requirement: Runner 重试必须支持可配置指数退避并复用单一退避实现

Runner 对被测 chatbot 的调用重试 MUST 支持可配置的指数退避，且退避数学 MUST 与 LLM 后端（`judges/llm_backend.py`）复用同一实现（`medeval/retry.py` 的 `backoff_delay`），禁止两处各写一套退避公式。

退避默认 MUST 关闭（`retry_backoff_base_s=0.0`）以保持既有"立即重试"行为不变；仅当显式配置正的退避基数时，Runner 才在重试之间插入退避。被测 bot 调用的端到端超时 MUST 由 Runner 单一权威施加（`asyncio.wait_for`），适配器底层客户端超时仅作安全网。

#### Scenario: 默认配置行为不变

- **当** `retry_backoff_base_s` 取默认 `0.0` 且某轮调用失败需重试
- **那么** Runner MUST 不插入任何 sleep，重试时序与改造前逐位一致

#### Scenario: 启用退避后按指数等待

- **当** 配置 `retry_backoff_base_s > 0` 且某轮调用连续失败
- **那么** 第 N 次重试前 MUST 等待 `backoff_delay(N, base=retry_backoff_base_s, ...)` 秒，并受 `retry_backoff_max_s` 封顶

#### Scenario: 退避数学单一真值源

- **当** LLM 后端与 Runner 都需要指数退避
- **那么** 二者 MUST 调用同一 `backoff_delay` 实现，禁止复制各自的退避公式
