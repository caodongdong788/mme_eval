# Tasks

- [x] 1. 前端：用例详情回退到看板「用例明细」tab（看板 tab 记忆）
- [x] 2. 后端：`JudgeModelConfig` 表（+ `has_api_key` 属性）
- [x] 3. 后端：schemas `JudgeModelOut`(掩码)/`JudgeModelCreate`/`JudgeModelUpdate` + `RunCreate.judge_model_id`
- [x] 4. 后端：`routers/judge_models.py` CRUD（名称唯一 409、Key 只写不读）+ `app.py` 注册
- [x] 5. 后端：`runs.create_run` 据 `judge_model_id` 构建 judge 覆盖（注入 Key，public 剔除）
- [x] 6. TDD：`tests/server/test_judge_models.py`（CRUD + 掩码 + launch 注入）
- [x] 7. 前端 `api.ts`：JudgeModel 类型 + listJudgeModels/create/update/delete
- [x] 8. 前端：`JudgeModelsPage.tsx` 配置页 + `App.tsx` 菜单/路由
- [x] 9. 前端：`LaunchPage.tsx` 打分模型改为下拉选择 `judge_model_id`
- [x] 10. 验证：pytest + tsc + build + 浏览器走查 + graphify update + openspec validate/archive
