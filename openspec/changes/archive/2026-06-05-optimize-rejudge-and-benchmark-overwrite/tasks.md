# Tasks

## 功能 1：判据覆盖保存
- [x] 1.1 `server/benchmarks.py`：`overwrite_benchmark_from_yaml(session, target, yaml_text)`（复用合并语义、写回源集、内置拒绝）
- [x] 1.2 `server/schemas.py`：`OverwriteBenchmarkYamlRequest{ yaml_text }`
- [x] 1.3 `server/routers/benchmarks.py`：`POST /{id}/overwrite-yaml`（422 校验失败 / 400 内置 / 零匹配报错）
- [x] 1.4 测试：覆盖成功更新原集判据、未匹配用例保留、内置拒绝、零匹配报错

## 功能 2：重判优化
- [x] 2.1 `server/schemas.py`：`RejudgeRequest` 加 `judge_model_id` / `only_release_failed`
- [x] 2.2 `server/routers/runs.py`：`rejudge_run` 解析 `judge_model_id`→judge 覆盖；`only_release_failed` 且源无失败用例→400
- [x] 2.3 `server/eval_job.py`：`build_rejudge_job(only_release_failed=...)` 只判失败子集 + 合并源报告 + `build_report` 重算 + 复制全部留痕
- [x] 2.4 测试：judge_model_id 解析正确；只重判失败=通过用例沿用源结果、失败用例分数更新、总分重算；全量路径不变；无失败用例 400

## 前端
- [x] 3.1 YAML 弹框加「覆盖当前 benchmark」（内置禁用 + 二次确认），调 `overwrite-yaml`
- [x] 3.2 重判弹框：judge 改判分模型库下拉（去手填）；加「只重判上线失败」勾选；`api.ts` 类型/接口
- [x] 3.3 前端 tsc typecheck + vite build 通过

## 验证 / 收尾
- [x] 4.1 `pytest` 全量绿（525 passed）
- [x] 4.2 `medeval run --config config.yaml --dry-run` 通过
- [x] 4.3 `graphify update .` 刷新图谱
- [ ] 4.4 `openspec validate --strict` 通过后 `openspec archive`
