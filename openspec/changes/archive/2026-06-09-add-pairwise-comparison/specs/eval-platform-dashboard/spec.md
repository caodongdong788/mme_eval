## ADDED Requirements

### Requirement: Pairwise 对比入口

看板 SHALL 提供「Pairwise 对比」入口，允许用户选择两次评测（A 基线 / B 本次）与一个
裁判模型并发起对比。当所选两个 run 不可比（判分尺子不同/benchmark 不同/用例集合不
一致/缺 trace）时，界面 MUST 给出中文错误提示而非静默失败。

#### Scenario: 选择两次 run 发起对比
- **WHEN** 用户在入口选定两个可比的 run 与裁判模型并提交
- **THEN** 界面创建一次比较并跳转到结果页（展示进行中状态）

#### Scenario: 不可比时报错
- **WHEN** 用户选择判分尺子不同的两个 run
- **THEN** 界面 MUST 展示「判分尺子不同不可比」的中文提示

### Requirement: Pairwise 结果展示

结果页 SHALL 含三块：①整体总结（哪次质量更高、胜/平/负、按维度胜率、回退用例清单、
被测差异 `subject_diff`）；②逐用例对比列表（可按 `winner` 筛选/排序）；③单题详情——
A/B 完整对话左右并排、该题判定理由与各维度归属。回退用例（B 更差）MUST 可被显著标识
以便人工复核。

#### Scenario: 查看整体总结
- **WHEN** 比较完成
- **THEN** 顶部展示整体结论与按安全/功能/体验维度的胜率，并列出回退用例

#### Scenario: 下钻单题对比
- **WHEN** 用户点击列表中某用例
- **THEN** 展示 A/B 完整对话左右并排与该题判定理由
