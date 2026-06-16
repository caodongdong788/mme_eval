# Proposal: LLM 判官 QPM 限频优化

## Why

AIDP/GPT 判官返回 429 `qpm limit`；`run.concurrency` 同时约束 bot 与 LLM 判官，92 题评测时突发并发过高，退避窗口内仍被限流。

## What

- `run.judge_concurrency` + `run.llm_min_interval_s`：判官阶段与 bot 并发解耦
- `LLMBackend` 全局并发槽 + 最小调用间隔（llm / scoring_point / semantic 共用）
- QPM 错误退避至少 60s；`max_retries` 提至 6
