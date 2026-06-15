## ADDED Requirements

### Requirement: 离线重判命令 rejudge

evaluation-cli MUST 提供 `medeval rejudge <run_dir>` 命令：对已落盘的冻结用例与冻结会话留痕重跑判分与评分，**MUST NOT 调用 adapter**。冻结用例 MUST 取自 `<run_dir>/report.json` 的 `results[*].case`（保证用例不随 `cases/` 后续改动而变），冻结留痕 MUST 取自 `<run_dir>/traces.jsonl.gz`。当 `traces.jsonl.gz` 缺失但原 run `n_runs==1` 时 MUST 回退用 `report.json` 的代表性 trace 重判；当 `n_runs>1` 且留痕缺失时 MUST 报清晰错误（代表性 trace 不足以重做 voting）。rejudge 结果 MUST 写入**新** run 目录并默认与原 run 做 diff。

#### Scenario: 同 config 重判结果一致

- **WHEN** 对一个已落盘 run 用与原 run 相同的 config 执行 `rejudge`
- **THEN** 各 judge verdict 与综合分 MUST 与原 run 一致，且全程 MUST NOT 产生任何 adapter 调用

#### Scenario: 缺留痕且多轮投票无法重做

- **WHEN** `rejudge` 目标缺 `traces.jsonl.gz` 且原 run `n_runs>1`
- **THEN** 系统 MUST 报清晰错误而非给出不完整的重判结果

### Requirement: 断点续跑选项 run --resume

evaluation-cli 的 `medeval run` MUST 提供 `--resume <run_dir>` 选项，按 dialog-runner 的断点续跑契约复用 `<run_dir>` 中成功的会话留痕、仅重跑缺失/失败者，并写入新的 run 目录。

#### Scenario: 续跑写新目录

- **WHEN** 以 `--resume <prev_dir>` 发起评测
- **THEN** 系统 MUST 复用 prev 成功留痕、补跑其余用例，并把完整结果写入一个新的 run 目录

### Requirement: 存储治理命令 prune 与自动清理

evaluation-cli MUST 提供 `medeval prune` 命令按 retention 策略清理历史 run 的胖产物（`traces.jsonl.gz` / `transcripts.xlsx` / 残留 `traces.partial.jsonl`），并 MUST 支持 `--dry-run` 仅预览不删除。清理 MUST 永久保留每个 run 的 `report.json`，MUST 豁免含 `KEEP` sentinel 文件的 run 目录（当 `keep_tagged=true`）。`medeval run` 收尾 MUST 在 `run.retention.enabled` 为真时自动触发同一清理逻辑。

#### Scenario: 清胖留瘦且豁免标记目录

- **WHEN** 历史 run 数量超过 `keep_last`，其中某 run 目录含 `KEEP` 文件
- **THEN** 超额 run 的胖产物 MUST 被删除、`report.json` MUST 保留，含 `KEEP` 的 run MUST 完整保留

#### Scenario: dry-run 只预览

- **WHEN** 执行 `medeval prune --dry-run`
- **THEN** 系统 MUST 仅列出将被清理的产物，MUST NOT 实际删除任何文件
