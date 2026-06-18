## ADDED Requirements

### Requirement: 判分模型 Prompt 双栏编辑

判分模型新建/编辑弹窗 MUST 采用双栏布局：左侧 MUST 提供 judge `prompt_template` 多行输入；右侧 MUST 保留现有模型连接参数，且 Temperature MUST 以横向滑条（「回复随机性」）展示并双向绑定数值。左侧 MUST 提供「Prompt 质检」按钮：点击 MUST 调用 `POST /api/judge-models/optimize-prompt` 并将返回的优化正文写回 prompt 输入框；请求进行中 MUST 展示 loading 且禁止重复提交。

#### Scenario: 质检优化 prompt

- **WHEN** 用户在编辑弹窗输入草稿 prompt 并点击「Prompt 质检」
- **THEN** 前端 MUST 调用 optimize 接口并将 `optimized_prompt` 回填到 prompt 输入框

#### Scenario: Temperature 滑条

- **WHEN** 用户拖动「回复随机性」滑条
- **THEN** 表单 temperature 字段 MUST 同步更新且在保存时提交后端
