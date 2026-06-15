## ADDED Requirements

### Requirement: 系统必须为每次评测额外输出 transcripts.xlsx 完整对话流水

每次 `medeval run` 完成后系统 MUST 在 `outputs/<run>/transcripts.xlsx` 写出一份独立的 Excel 文件，含两个 sheet：

**Sheet 1：概览**
- 工作表名：`概览` 或 `Overview`
- 列（按顺序）：`sample_id` / `level` / `depth`（int，对话中 user 轮数）/ `scenario` / `passed`（True/False）/ `stability`（stable_pass / flaky / stable_fail）/ `failure_tags`（逗号分隔字符串）
- 1 行 = 1 个 case；行序按 case 在 RunReport 中的原始顺序

**Sheet 2：对话流水**
- 工作表名：`对话流水` 或 `Transcripts`
- 列（按顺序）：`sample_id` / `turn`（int，N 从 1 开始；system 标 0）/ `role`（user / bot / system）/ `content`（字符串，cell 必须开启 wrap_text）
- 1 行 = 1 个 turn；同一 case 的所有 turn 必须按时间顺序连续排布，case 之间的边界由 `sample_id` 列变化标识

xlsx 写盘 MUST 使用 `openpyxl` 库；列宽 MUST 适配阅读：`content` 列默认宽度 80、其他列默认 15。

#### 场景: 40 case 双 sheet 完整生成

- **WHEN** 一次跑评测出 40 个 case，平均每个 case 3.5 个 turn
- **THEN** transcripts.xlsx Sheet 1 必须有 40 行（+ 1 行 header），Sheet 2 必须有约 140 行（40 × 3.5 = 140）；任意 case 的 turn 必须在 Sheet 2 中连续

#### 场景: 包含 system 预设 turn

- **WHEN** 某 case 的 trace 含 system turn
- **THEN** 该 system turn 必须在 Sheet 2 中以 `role=system, turn=0` 单独出现（不与 user/bot turn 编号冲突）

#### 场景: content 自动换行

- **WHEN** 某 turn 的 bot 回复包含 5 段长文本
- **THEN** Sheet 2 中 `content` cell 必须开启 wrap_text，飞书表格 / Excel 打开时不截断

#### 场景: stability 字段在 N=1 时仍正确填充

- **WHEN** 用户 `--repeat 1` 跑（无 N-runs）
- **THEN** Sheet 1 的 `stability` 列必须填 `stable_pass` 或 `stable_fail`（基于 overall_passed 推断），不得为空

### Requirement: transcripts.xlsx 必须发布为飞书表格

`publish_xlsx_to_lark(path, parent_folder_token, title)` MUST 调用本机 `lark-cli` 把 xlsx 上传为飞书 Sheet 文档，成功返回 sheet URL，失败返回 None 并记录 warning（不抛异常）。命名约定 MUST 为 `{run_name} · 对话流水`。

报告 markdown 末尾 MUST 追加一行 `**完整对话流水**：<lark_sheet_url>`（lark URL 不可用时显示本地 xlsx 路径），让评审从报告跳到对话流水。

#### 场景: 飞书 sheet 上传成功

- **WHEN** lark-cli 可用、xlsx 可读、网络通畅
- **THEN** 调用返回飞书 sheet URL；终端打印 `✓ 飞书对话流水已发布：<url>`；markdown 末尾含该 URL

#### 场景: lark-cli 未安装时降级

- **WHEN** PATH 中找不到 lark-cli
- **THEN** `publish_xlsx_to_lark` 返回 None；markdown 末尾改为追加本地路径 `**完整对话流水**：outputs/<run>/transcripts.xlsx`；终端只打 warning，主流程不中断

#### 场景: 与飞书报告 docx 的关联

- **WHEN** 一次评测同时发布报告 docx + 对话流水 sheet
- **THEN** 两者必须是同一 `parent_folder_token` 下的两份文档；命名 prefix 必须使用相同 `run_name`，便于飞书侧按 prefix 检索同一跑次的产物
