## ADDED Requirements

### Requirement: 报告必须呈现延迟统计且标注仅记录不计分

markdown 报告 MUST 新增"性能（仅记录）"段，呈现 `RunReport.latency_summary` 的延迟统计（至少 平均、中位、P90、最大，单位 ms）。该段 MUST 明确标注延迟"仅记录、不计分、不否决"，并 MUST 与通过率、软分等评分类信息分区呈现，避免被误读为性能合格线。当无任何成功 run 的延迟数据时，该段 MUST 显示为不适用而非渲染空表。

#### Scenario: 展示延迟统计

- **WHEN** 一次评测有可用延迟数据
- **THEN** 报告 MUST 输出 avg/median/p90/max 延迟，并附"仅记录、不计分"标注

#### Scenario: 无延迟数据时不渲染空表

- **WHEN** 全部 run 均失败、无可用延迟数据
- **THEN** "性能（仅记录）"段 MUST 显示为不适用（N/A），MUST NOT 渲染空表格
