## ADDED Requirements

### Requirement: Markdown 报告失败标签必须以中文短标签 label_zh 渲染

`render_markdown` 在两处渲染失败标签时 MUST 调用 `_tag_to_zh_label(tag_str: str) -> str` helper，把英文 enum value 转成对应的中文短标签 `FailureTag.label_zh`：

1. 概览段「失败归因 Top 标签」表的「标签」列
2. 失败样本段每条 case 的 `**失败标签：** ...` 行（多个 tag 用 `, ` 拼接）

`_tag_to_zh_label` MUST 在传入字符串无法构造 `FailureTag` 时降级返回原字符串（不抛 `ValueError`），以兼容历史 `report.json` 中已下线的 tag value。Markdown 报告 MUST 不再出现英文 snake_case 形式的失败标签 enum value。

`report.json`、Excel transcript（`transcripts.xlsx`）、`failure_tag_counter` 字段的 key 等机器可读输出 MUST 仍写英文 enum value，不受本需求影响。

#### Scenario: 失败样本段渲染中文短标签

- **WHEN** 一条 fail case 的 `failure_tags=["constraint_violation","missed_red_flag"]`
- **THEN** Markdown 失败样本段对应行 MUST 输出 `**失败标签：** 触发禁词, 漏报红旗`（不出现 `constraint_violation` / `missed_red_flag` 字面量）

#### Scenario: 失败归因 Top 标签表渲染中文

- **WHEN** `failure_tag_counter = {"constraint_violation": 3, "inquiry_incomplete": 3, "improper_prescription": 2}`
- **THEN** 概览段表格 MUST 形如 `| 触发禁词 | 3 |` / `| 问诊不足 | 3 |` / `| 越界处方 | 2 |`，不出现英文 enum value

#### Scenario: 历史 report.json 含未知 tag 时降级

- **WHEN** 重新渲染一份历史 `report.json`，其中含当前 `FailureTag` 已删除/重命名的 tag 字符串（如 `"legacy_old_tag"`）
- **THEN** Markdown 渲染 MUST 不抛错，该 tag 原文保留 `legacy_old_tag` 显示在标签列；其它已知 tag 仍正常渲染中文

#### Scenario: 失败标签数量为零时显示「—」

- **WHEN** 一次评测全部 case 通过，`failure_tag_counter` 为空 dict
- **THEN** 概览段 Top 标签表 MUST 维持现有行为输出 `| — | — |`，不渲染中文短标签（无内容可渲染）

#### Scenario: report.json 字段保持英文 enum value

- **WHEN** 同一份评测产物，`report.json` 与 `report.md` 同时落盘
- **THEN** `report.json` 中 `failure_tags` / `failure_tag_counter` MUST 仍是英文 enum value（如 `"missed_red_flag"`），仅 `report.md` 渲染中文；二者由 `_tag_to_zh_label` 渲染层桥接

### Requirement: Excel transcripts.xlsx 失败标签列必须保持英文 enum value

`transcripts.xlsx` Sheet 1 概览的 `failure_tags` 列 MUST 写英文 enum value（逗号分隔），不渲染 `label_zh`。Excel 是面向下游分析脚本的稳定 schema，外部 pandas / dashboard 集成依赖英文 stable key。

#### Scenario: Excel 概览失败标签列写英文

- **WHEN** 一条 fail case `failure_tags=["constraint_violation","missed_red_flag"]` 写入 `transcripts.xlsx` Sheet 1
- **THEN** 该行 `failure_tags` cell MUST 等于 `"constraint_violation, missed_red_flag"`（不出现 `触发禁词`）
