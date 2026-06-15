## ADDED Requirements

### Requirement: N-runs 会话留痕落盘为可复现产物

dialog-runner MUST 能把每条用例的全部 N-runs `ConversationTrace` 落盘为可复现产物 `outputs/<run>/traces.jsonl.gz`（gzip + jsonl），并 MUST 在 run 阶段**增量写入**（每完成一个 `(sample_id, run_idx)` 即追加），使 run 阶段中途崩溃时已完成的留痕不丢失。落盘 MUST 受 `run.persist_traces` 开关控制，且当 `evaluate()` 未被告知输出目录时 MUST NOT 落盘（保持现状行为）。

落盘记录 MUST 按 `run.store_raw` 对 `raw_responses` 瘦身：`never` MUST 清空所有 `raw_responses`；`on_error` MUST 仅在该留痕 `error` 非空时保留 `raw_responses`、成功留痕清空；`always` MUST 原样保留。瘦身 MUST 不改动 `messages`/`turn_latencies_ms`/`error` 等离线重判所需字段。

#### Scenario: 默认开启增量落盘

- **WHEN** `medeval run` 使用默认配置（`persist_traces=true`、`store_raw=on_error`）完成一次评测
- **THEN** `outputs/<run>/traces.jsonl.gz` MUST 存在且可解析回每条用例的 N-runs 留痕，成功轮次的 `raw_responses` MUST 为空、报错轮次 MUST 保留

#### Scenario: 未告知输出目录时不落盘

- **WHEN** `evaluate()` 在未传入输出目录的场景（平台 / SDK / 测试）执行
- **THEN** MUST NOT 写任何 trace 产物，且判分产物与进度 phase MUST 与本次变更前逐字段一致

### Requirement: 基于已落盘成功留痕的断点续跑

dialog-runner MUST 支持断点续跑：给定上一次 run 的落盘留痕，执行 MUST 复用其中 `error` 为空的 `(sample_id, run_idx)` 留痕、SHALL NOT 对其重复调用 adapter，仅对缺失或失败的 `(sample_id, run_idx)` 重新执行。续跑 MUST 校验 adapter 指纹：当前配置的 adapter 指纹与落盘 meta 不一致时 MUST 拒绝复用并报清晰错误，MUST NOT 把不同 bot 的旧留痕混入本次结果。断点续跑 MUST 仅对 `local` 执行后端生效；当 `run.executor=ray` 且请求续跑时 MUST 抛清晰错误而非静默忽略。

#### Scenario: 复用成功留痕、重跑失败留痕

- **WHEN** 以 `--resume <prev_dir>` 续跑，且 prev 中部分用例成功、部分 `error` 非空
- **THEN** 成功的 `(sample_id, run_idx)` MUST 直接复用（不调 adapter），失败/缺失者 MUST 重新执行，最终产物结构与正常 run 一致

#### Scenario: adapter 指纹不一致拒绝续跑

- **WHEN** 续跑目标的 adapter 指纹与当前配置不一致
- **THEN** 系统 MUST 报错终止，MUST NOT 复用旧留痕
