# Design: 判分模型 Prompt 编辑

## 数据模型

`judge_model_config.prompt_template TEXT NULL` — 完整 judge prompt 模板，MUST 支持占位符 `{conversation}`、`{rubric_text}`、`{tool_context}`。空或 NULL = 运行时沿用 `medeval/judges/llm.py` 内置 `_PROMPT_TEMPLATE`。

## Prompt 质检

`POST /api/judge-models/optimize-prompt` body: `{ "prompt": "..." }` → `{ "optimized_prompt": "..." }`。

- 使用 `load_config(MEDEVAL_CONFIG_PATH).judges.llm` 构造 `LLMBackend`（与平台默认 judge 一致）。
- Meta-prompt：要求保留占位符与 JSON 输出结构，医疗评测保守口径，仅返回优化后正文。
- LLM 失败 → 422 + 可读 detail；未配置 key → 503。

## 判分注入

`JUDGE_OVERRIDE_KEYS` 增加 `prompt_template`；`JudgeOverride` / `runs.py` / `rejudge_launch.py` 从 `JudgeModelConfig` 拷贝。`build_judges` → `LLMJudge(prompt_template=...)`。

## 前端

Modal 宽 ~960px，CSS grid 两列。左：`Input.TextArea` + 「Prompt 质检」主按钮；右：现有字段，`Temperature` 改为 Slider+数字（标签「回复随机性」）。hook 调 optimize API 后 `form.setFieldValue('prompt_template', result)`。
