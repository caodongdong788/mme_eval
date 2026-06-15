## Why

借鉴 OpenCompass `Inference → Evaluation` 解耦范式：medeval 目前 run（调 chatbot）与 judge（判分）在同一进程连跑，`ConversationTrace` 只活在内存。这带来两个实际痛点：

1. **判分逻辑无法单变量 diff**：README 标榜用 judge fingerprint 区分「判分逻辑变化」vs「bot 表现变化」，但只要重判就必须重新调 chatbot，bot 输出本身会漂移，等于无法冻结变量、且重花 adapter 成本。
2. **崩溃无成本止损**：`run.repeat=3` × 71 条 × 多轮 × LLM judge 的进度一旦中途崩溃全部作废，从头再来。

同时，一旦把 trace 落盘，产物会随评测次数线性膨胀（`raw_responses` 原始体是大头），必须**同时**设计存储治理，否则只落不清会撑爆磁盘。

## What Changes

- **trace 落盘**（dialog-runner / reporting）：把每条用例的 `ConversationTrace`（含 N-runs）作为一等产物写入 `outputs/<run>/traces.jsonl.gz`（gzip + jsonl，零新依赖）。run 阶段**增量流式**写入（崩溃也留下已完成部分），run 阶段结束即落定。
- **store_raw 瘦身**（dialog-runner）：新增 `run.store_raw: never|on_error|always`，默认 `on_error`——成功轮次丢弃冗长 `raw_responses`、仅报错轮次留全量（重判只读 `messages` 文本，无损）。
- **离线重判 `medeval rejudge`**（evaluation-cli，新能力）：对冻结 trace + 冻结用例重跑判分+评分，**零 adapter 调用**，输出到新 run 目录并默认与原 run diff。
- **断点续跑 `medeval run --resume <dir>`**（dialog-runner / evaluation-cli）：复用上次已成功的 `(sample_id, run_idx)` trace，只重跑缺失/失败者；adapter 指纹不匹配时拒绝复用（绝不拿错 bot 的旧 trace）。
- **存储治理 retention/prune**（reporting / evaluation-cli，新能力）：新增 `run.retention`（`keep_last`/`ttl_days`/`keep_tagged`）+ `medeval prune` 子命令：滚动清理胖产物（`traces.jsonl.gz`/`transcripts.xlsx`），但 `report.json` 永久保留、`KEEP` 标记目录永久豁免。run 收尾自动触发。

默认配置下（`store_raw=on_error`、`persist_traces=true`、`retention.keep_last=20`）现有判分行为与 fingerprint 完全不变；不引入新依赖；不触碰 `TestCase`/`BaseJudge`/`FailureTag`/HardGate 启发式。

## Capabilities

### New Capabilities
- 无新增独立 capability spec；能力以 ADDED/MODIFIED requirement 落到现有 `dialog-runner` / `evaluation-cli` / `reporting`。

### Modified Capabilities
- `dialog-runner`: 执行 MUST 可把 N-runs 会话留痕落盘为可复现产物，并 MUST 支持基于已落盘成功留痕的断点续跑（adapter 指纹校验）。
- `evaluation-cli`: CLI MUST 提供 `rejudge`（离线重判）、`run --resume`（断点续跑）、`prune`（存储治理）三项入口。
- `reporting`: 落盘的会话留痕 MUST 支持 store_raw 瘦身与 retention 滚动清理，且 `report.json` MUST 永久保留以保证跨版本 diff 不断链。

## Impact

- 代码：`medeval/trace_store.py`（新）、`medeval/retention.py`（新）、`medeval/service.py`（抽 `run_traces`/`judge_traces`、evaluate 编排 + 落盘/续跑/finalize）、`medeval/runner/executor.py`（resume_index）、`medeval/config.py`（`RunCfg.store_raw`/`persist_traces`/`RetentionCfg`）、`medeval/cli.py`（`rejudge`/`run --resume`/`prune` + 收尾 retention）、`config.yaml`、`tests/`。
- 兼容性：所有新增配置字段带默认值且默认值=现状语义；`evaluate()` 新增形参均为可选、缺省时行为与现状逐字段一致（平台 `server/eval_job.py` 调用无需改）；历史 `report.json` 与判分行为不变；judge fingerprints 不变。
- 依赖：仅用标准库 `gzip`/`json`；无新增第三方依赖。
- 非目标：外置对象存储（S3/OSS/飞书）作为胖产物 system-of-record；平台 DB 侧 case_result retention；ray 后端的增量续跑（resume 仅 local 后端支持，ray + resume MUST 报清晰错误）。
