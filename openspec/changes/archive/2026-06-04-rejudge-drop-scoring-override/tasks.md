# Tasks

- [x] 1. 后端：`RejudgeRequest` 去 `scoring`；`eval_job` 删 `_apply_scoring_override` 与
  `build_rejudge_job(scoring_override=…)`、`ScoringCfg` 导入；`runs.py` 调用处去 `scoring_override`
- [x] 2. 前端：`RejudgePayload` 去 `scoring`；弹框删四模块权重/扣分步长表单与 `DEFAULT_MODULE_MAX`、
  无用 import（InputNumber/Divider 若仅此处用）；文案改为「换 judge 模型」
- [x] 3. 测试：删 scoring 相关用例，端点测试改测 judge/cases_benchmark_id 透传
- [x] 4. 验证：全量 pytest + tsc + `medeval run --dry-run` + `graphify update .` + openspec archive
