# Design: Pairwise 并发执行与安全落库

## 并发模型（两层）

```
run_pairwise_comparison
  └─ Semaphore(N)            ← 题间并发：同时在跑 N 道题的 compare_case
       └─ compare_case
            └─ asyncio.gather(顺序①, 顺序②)   ← 题内并行：两次裁判同时调
```

- N = `JudgeModelConfig.pairwise_concurrency`（默认 4），发起对比时随判分模型读取。
- 题内并行只在 `swap_debias=True` 生效；`swap_debias=False` 单次调用无并行对象。

## 安全落库与进度（关键）

并发下若多协程各自 `session_scope()` 写 verdict + 累加 `done_cases`，SQLite 单写会
`database is locked`，且内存计数 `len(verdicts)` 非原子、进度会跳变。

策略：
- **LLM 调用并发、DB 写串行**。用一个 `asyncio.Lock` 包住「写 PairwiseCaseVerdict +
  递增 done_cases」临界区。裁判调用（慢、I/O）在锁外并发；DB 写（快）在锁内逐个完成。
- `done_cases` 用独立计数器在锁内 `+= 1`，保证单调递增。
- verdict 顺序不再严格等于 `common` 顺序（并发完成），最终 `summary` 由全部 verdict 汇总，
  与顺序无关；逐用例列表前端本就按 winner/sample 展示，不依赖落库顺序。

## 为何不动主评测链路

`config.run.concurrency` 同时管被测 bot 调用与三个 judge 的并发，是 run 级语义；
本变更范围限定 Pairwise（裁判纯 LLM I/O、无被测 bot），并发度挂在判分模型上仅供对比使用，
评测端 `service.py` 不读该字段，行为零变化。

## fingerprint 不变

并发是执行方式，不影响判分语义。`PairwiseComparator.fingerprint()` 不纳入并发度，
旧对比与新对比在 diff 上不因并发改动而判为「判分逻辑变化」。
