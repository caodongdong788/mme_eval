# Design

## 目录命名

`run_slug = f"{run.name}_{int(datetime.now().timestamp() * 1000)}"`。

- 选毫秒级 Unix 时间戳而非 `YYYYmmdd_HHMMSS`：`run.name` 通常已含年月日+版本号（如 `..._2026_05_29_v1`），避免重复日期；毫秒精度顺带消除秒级连跑撞名。
- `run_slug` 同时作为 `report.run_name`，使报告标题、飞书文档名、`--diff-against` 引用三者用同一标识，避免「逻辑名 vs 目录名」二义。

## 自动对比上一次

`_find_previous_run` 按 `outputs/*/report.json` 的 mtime 取「除本次外最近一次」。因为本次的 `report.json` 已先写盘，必须按解析后的当前目录路径排除自身，再取次新者——即时间上的上一次评测。

## 对比目标优先级

`--diff-against`（CLI）> `reporter.diff_against`（config）> 默认。取值语义：

| 值 | 行为 |
|---|---|
| 留空 / `auto` | 自动对比上一次 |
| 具体目录名 | 对比 `outputs/<名>/report.json`；不存在则提示并跳过 |
| `none` / `off` | 关闭对比 |

## 兼容与边界

- 旧用法「`reporter.diff_against: <run名>`」仍生效（落入「具体目录名」分支）。
- 首次评测无历史可比 → 跳过 diff，不报错。
- 不触碰判分逻辑：hard_gate / rule / llm / scoring_point / semantic_adjudicator 指纹均不变。
