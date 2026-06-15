## ADDED Requirements

### Requirement: 落盘留痕的 store_raw 瘦身与 retention 滚动清理

reporting MUST 把落盘的会话留痕视为可滚动清理的「胖产物」，并保证跨版本 diff 不断链：`report.json` MUST 永久保留（不被 retention 清理），胖产物（`traces.jsonl.gz` / `transcripts.xlsx` / 残留 `traces.partial.jsonl`）MUST 受 `run.retention` 控制按 `keep_last`（按修改时间保留最近 N 个 run，0 表示全留）与可选 `ttl_days` 滚动清理。当 `keep_tagged=true` 时，含 `KEEP` sentinel 的 run 目录 MUST 永久豁免。

落盘留痕的体积 MUST 可经 `run.store_raw` 控制：瘦身只影响 `raw_responses`，MUST NOT 影响 `report.json` 中任何聚合指标与判分结论。

#### Scenario: report.json 不被清理保证 diff 不断链

- **WHEN** retention 清理了某历史 run 的胖产物
- **THEN** 该 run 的 `report.json` MUST 仍然存在，跨版本 diff 与趋势 MUST 仍可基于它进行

#### Scenario: 稳态磁盘有界

- **WHEN** 在 `keep_last=N` 下持续累积远多于 N 次评测
- **THEN** 保留的胖产物 run 数 MUST 收敛到约 N 个（加上 `KEEP` 豁免者），不随评测次数线性增长
