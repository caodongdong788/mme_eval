## ADDED Requirements

### Requirement: 报告必须呈现 token/cost 统计且标注仅观测不计分

markdown 报告 MUST 新增"成本 / Token（仅观测）"段，呈现 `RunReport.token_summary` 的 token 统计（至少总 token 与平均每 run token）。当 `config.yaml` 配置了非零单价时，该段 MUST 同时呈现折算成本（cost）与币种；未配置单价时 cost MUST 显示为 N/A 而非 0。该段 MUST 明确标注 token/cost "仅观测、不计分、不否决"，MUST 与评分类信息分区呈现，并 MUST 注明仅统计被测 bot（不含 judge 模型开销）。当无任何成功 run 的 token 数据时，该段 MUST 显示为不适用而非渲染空表。

#### Scenario: 展示 token 与 cost

- **WHEN** 一次评测有可用 token 数据且配置了单价
- **THEN** 报告 MUST 输出总 token / 平均每 run token / cost，并附"仅观测、不计分"标注

#### Scenario: 未配置单价仅出 token

- **WHEN** 有 token 数据但未配置单价
- **THEN** 报告 MUST 输出 token 统计，cost MUST 显示 N/A

#### Scenario: 无 token 数据时不渲染空表

- **WHEN** 全部 run 失败或后端从不返回 usage
- **THEN** "成本 / Token（仅观测）"段 MUST 显示为不适用（N/A），MUST NOT 渲染空表格

### Requirement: 版本对比必须呈现 token/cost 变化且可降级

报告 diff MUST 基于两份报告的 `token_summary` 呈现 token（及配置单价时的 cost）的 当前 / 上版 / Δ 对比，并 MUST 标注"仅观测、不计分、不否决"。当上一版本报告缺 `token_summary`（历史报告）时，diff MUST 给出友好提示而非抛错。

#### Scenario: 两版均有 token 数据

- **WHEN** 当前与上一版报告均含 `token_summary`
- **THEN** diff MUST 输出总 token（及 cost）的当前/上版/Δ 对比

#### Scenario: 历史报告缺字段时降级

- **WHEN** 上一版报告无 `token_summary`
- **THEN** diff MUST 显示友好提示，MUST NOT 抛错
