# Tasks

## 1. 共享退避
- [x] 1.1 新增 `medeval/retry.py`：`backoff_delay`（纯函数）+ `retry_async`（异常驱动，sleep 运行时取 asyncio.sleep）

## 2. 复用
- [x] 2.1 `judges/llm_backend.py::chat_json` 改用 `retry_async`（行为逐位不变）
- [x] 2.2 `config.py::RunCfg` 增 `retry_backoff_base_s=0.0` / `retry_backoff_max_s=40.0`
- [x] 2.3 `runner/executor.py`：`_run_one`/`run_cases` 加可配退避（默认 0 不变），复用 `backoff_delay`；双层超时注释收敛
- [x] 2.4 `service.evaluate`：把 `config.run.retry_backoff_base_s/max_s` 透传给 `run_cases`

## 3. 测试
- [x] 3.1 `tests/test_retry.py`：backoff_delay 单调/封顶/jitter；retry_async 重试/非重试/达上限/sleep 次数与值
- [x] 3.2 `tests/test_executor_backoff.py`：base>0 按公式 sleep；base=0 零 sleep
- [x] 3.3 `test_llm_backend` 退避用例回归绿（patch 目标改 `medeval.retry`）

## 4. 验证
- [x] 4.1 全量 `pytest` 绿（309 passed）
- [x] 4.2 `medeval verify-heuristics` 通过
- [x] 4.3 真实 config `medeval run --dry-run` 通过
- [x] 4.4 `graphify update .` 刷新图谱
- [x] 4.5 `openspec validate --strict` 通过并归档
