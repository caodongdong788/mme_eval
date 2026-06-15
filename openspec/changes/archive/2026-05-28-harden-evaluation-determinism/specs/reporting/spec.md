## ADDED Requirements

### Requirement: RunReport 与 CaseResult 必须暴露 stability 三态

`CaseResult` MUST 新增字段 `stability: Literal["stable_pass","flaky","stable_fail"]`（默认 `stable_pass` 以向后兼容）、`n_runs: int`（默认 1）、`per_run_passed: list[bool]`（默认 `[overall_passed]`）。

`RunReport` MUST 新增聚合字段 `stability_distribution: dict[str, int]`，含三键 `stable_pass` / `flaky` / `stable_fail`，分别记录三类 case 的总数。Markdown / HTML / JSON 三态输出 MUST 渲染该分布。

#### 场景: N=1 时所有 case 的 stability 必须为 stable_pass 或 stable_fail

- **WHEN** 跑 `--repeat 1`，没有 flaky
- **THEN** `stability_distribution["flaky"]` MUST 等于 0；`stability_distribution["stable_pass"] + stability_distribution["stable_fail"]` MUST 等于 `total`

#### 场景: N=3 报告概览必须显示三态计数

- **WHEN** 一次 `--repeat 3` 跑出来 stable_pass=29 / flaky=8 / stable_fail=3
- **THEN** Markdown 报告概览段 MUST 显式显示 `稳定性分布: 3 次都过 29 / 抖动 8 / 3 次都挂 3`（精确措辞可调，但三个数必须可见）

#### 场景: 历史报告无 stability 字段时向后兼容

- **WHEN** 加载本 change 落地前生成的 `report.json`（顶层无 `stability_distribution`）
- **THEN** 加载 / `diff_runs` MUST 不抛错；缺失字段在新 schema 中按默认值填充（stable_pass = total - 任何已有 fail 计数、flaky=0、stable_fail = total - stable_pass）

### Requirement: 抖动 case 在失败样本列表中必须显式标注

Markdown / HTML 失败样本段 MUST 在每条 fail case 的标题旁边显式标注其 `stability` 值。`stable_fail` 标注 `[3 次都挂]`、`flaky` 标注 `[抖动 N/M]`（N=fail 次数，M=总次数）；`stable_pass` 不出现在失败样本列表中。

#### 场景: 抖动 case 标注

- **WHEN** 一条 case `n_runs=3`、`per_run_passed=[True,False,False]`、最终 fail
- **THEN** 失败样本标题必须类似 `[抖动 2/3] l4_mt_d4_authority_late_claim`，让评审者一眼看出"这是 N 次中挂了 2 次"

#### 场景: stable_fail 标注

- **WHEN** 一条 case `per_run_passed=[False,False,False]`
- **THEN** 失败样本标题必须类似 `[3 次都挂] l4_mt_d4_authority_late_claim`
