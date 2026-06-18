# Proposal: 判分模型 Prompt 编辑与质检

## Why

判分模型配置页目前只能配连接参数，无法自定义 LLM-as-Judge 的 prompt；列表也无法做 prompt 质量优化。评测工程师需要在平台内编辑 judge prompt，并用固定强模型做「Prompt 质检」。

## What

- 判分模型 CRUD 增加 `prompt_template`（空=沿用内核内置模板）。
- 新增 `POST /api/judge-models/optimize-prompt`：用 **config.yaml 默认 judges.llm** 连接调一次 LLM 优化用户草稿（与用户选的判分模型无关）。
- 发起评测/重判选用判分模型时 MUST 注入 `prompt_template` 到 `LLMJudge`。
- 前端编辑弹窗改为双栏：左 prompt + 质检按钮，右模型参数 + Temperature 滑条。

## Impact

- `server/models_db.py`, `server/schemas.py`, `server/services/judge_models.py`, `server/routers/judge_models.py`
- `medeval/config.py`, `medeval/judges/llm.py`, `medeval/service.py`
- `frontend/src/pages/JudgeModelsPage.tsx` + 新组件
- OpenSpec: `eval-platform-dashboard`, `eval-platform-service`, `judging-pipeline`
