# Design — 统一重试 / 退避策略

## `medeval/retry.py`

```python
def backoff_delay(attempt: int, *, base: float, factor: float = 2.0,
                  max_delay: float, jitter: float = 0.0) -> float:
    """第 attempt 次（0-indexed）重试前的等待秒数：min(max_delay, base*factor**attempt) + U(0,jitter)。"""
    raw = base * (factor ** attempt)
    d = min(max_delay, raw)
    if jitter:
        d += random.uniform(0, jitter)
    return d

async def retry_async(fn, *, max_retries, retryable, base, factor=2.0,
                      max_delay, jitter=0.0, on_retry=None, sleep=None):
    """异常驱动的指数退避重试。fn 为无参 async 工厂；retryable(exc)->bool 决定是否重试。"""
    _sleep = sleep or asyncio.sleep          # 运行时取 asyncio.sleep（尊重 monkeypatch）
    attempt = 0
    while True:
        try:
            return await fn()
        except Exception as e:
            if not retryable(e) or attempt >= max_retries:
                raise
            delay = backoff_delay(attempt, base=base, factor=factor,
                                  max_delay=max_delay, jitter=jitter)
            if on_retry:
                on_retry(attempt, e, delay)
            await _sleep(delay)
            attempt += 1
```

注：`sleep` 默认 `None` 后取 `asyncio.sleep`（而非默认参数捕获），确保 `monkeypatch.setattr(asyncio, "sleep", ...)` 能拦截——LLMBackend 现有测试正是这么打的桩。

## LLMBackend.chat_json 复用

```python
from openai import RateLimitError
from ..retry import retry_async

async def _create():
    return await self._client.chat.completions.create(model=..., messages=..., temperature=..., response_format={"type":"json_object"})

resp = await retry_async(
    _create,
    max_retries=max_retries,
    retryable=lambda e: isinstance(e, RateLimitError),
    base=5.0, factor=2.0, max_delay=40.0, jitter=2.0,
    on_retry=lambda attempt, e, wait: log.warning("%s 触发限速 (尝试 %d/%d)，等待 %.1fs 重试", self.owner, attempt+1, max_retries+1, wait),
)
text = resp.choices[0].message.content or "{}"
return json.loads(text)
```

行为对拍：`min(40, 5*2^attempt + U(0,2))` 与原式 `min(40.0, 2**attempt*5 + uniform(0,2))` 完全相同；调用次数 = max_retries+1；退避次数 = 失败次数；超上限 raise `RateLimitError`。`test_llm_backend` 三个退避测试（calls/sleeps 计数、raise）保持绿。

## executor 可配退避

`_run_one(case, adapter, timeout_s, retry, session_suffix, *, backoff_base_s=0.0, backoff_max_s=40.0)`：
- 失败 `continue` 前，若 `backoff_base_s > 0` 且非最后一次尝试：`await asyncio.sleep(backoff_delay(attempt, base=backoff_base_s, factor=2.0, max_delay=backoff_max_s))`。
- `backoff_base_s <= 0` → 完全不 sleep（与现状逐位一致）。
- executor 的失败是「值驱动」（`resp.error`）与「异常驱动」（TimeoutError/Exception）混合，结构上保留原循环，仅在 `continue` 前插入退避；不套 `retry_async`（避免把值驱动硬塞进异常驱动框架）。

`run_cases(..., retry=2, retry_backoff_base_s=0.0, retry_backoff_max_s=40.0)` 新增两个带默认 kwargs，透传给 `_run_one`。`service.evaluate` 从 `config.run.retry_backoff_base_s/max_s` 读取并传入。

## config

`RunCfg` 增：`retry_backoff_base_s: float = 0.0`、`retry_backoff_max_s: float = 40.0`。默认 0 = 关闭退避，行为不变。

## 双层超时

以注释固化：executor 的 `asyncio.wait_for(timeout_s)` 是端到端单一权威超时；openai 客户端 `timeout=timeout_s` 仅作底层安全网（防止 SDK 在极端情况下挂死）。不改数值、不改行为。

## 测试（TDD）

- `tests/test_retry.py`：`backoff_delay` 单调/封顶/jitter 区间；`retry_async` 在 retryable 时重试、非 retryable 立即抛、达 max 抛最后异常、`on_retry`/`sleep` 调用次数与 delay 值（注入 sleep 收集）。
- executor 退避：fake adapter 首次 error 后成功 + `retry=1`，`retry_backoff_base_s>0` → 注入/捕获 sleep，断言按 `backoff_delay` 等待；`base=0` → 零 sleep。
- `test_llm_backend` 三退避用例回归绿。
- 全量 pytest + verify-heuristics + 真实 config `--dry-run`。
