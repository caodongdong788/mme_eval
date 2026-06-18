# Proposal: judge-model-prompt-default-validate

## Why

新增判分模型时用户需手动粘贴内置 prompt；保存与质检缺少统一格式门禁，易导致运行时 `.format()` 失败或 JSON 输出结构不符。

## What

- 新增模型默认填入 `DEFAULT_PROMPT_TEMPLATE`
- 创建/更新保存时强制 `validate_judge_prompt_template`
- Prompt 质检 meta-prompt 与输出均须通过同一校验
- `GET /api/judge-models/default-prompt` 供前端取默认正文

## Success

- 无效 prompt 保存返回 422
- 质检结果必含三占位符且可 `.format()`、含 scores/reasons/flags 说明
- 相关 pytest 绿
