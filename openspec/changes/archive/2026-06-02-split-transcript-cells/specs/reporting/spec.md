## ADDED Requirements

### Requirement: transcripts.xlsx 内容派生与排版分层且 profile 至多解析一次

transcripts.xlsx 导出 MUST 把"纯内容派生"（文本截断、折行估算、关键词标记、得分点/维度单元格文本）与"openpyxl 排版/写入"分置于不同模块：内容派生 MUST 为无副作用的纯函数，可独立单测；排版层 MUST 只负责 sheet/列宽/行高/样式写入。

导出每个 case 时，其评分 profile（`resolve_profile`）MUST 至多解析一次，解析结果（`module_max` 与 `name`）MUST 复用给所有需要它的内容派生函数，禁止同一 case 多次重复解析。改造 MUST 保持 xlsx 产物与改造前等价（内容与样式不变）。

#### Scenario: 内容派生可独立测试

- **当** 需要验证关键词标记或文本折行逻辑
- **那么** 测试 MUST 能直接导入纯内容派生函数断言，无需构造 openpyxl workbook

#### Scenario: 每个 case 仅解析一次 profile

- **当** 导出某个 case 的行（需要 `module_max` 与 profile `name`）
- **那么** 该 case 的 `resolve_profile` MUST 只被调用一次，结果复用给各列

#### Scenario: 产物等价

- **当** 对同一 RunReport 导出 transcripts.xlsx
- **那么** 拆分/去重后的产物 MUST 与改造前在内容与样式上等价
