# Tasks

## 1. DB schema + 迁移
- [ ] 1.1 `EvalRun` 增 `has_traces` / `pinned`(index) / `parent_run_id`
- [ ] 1.2 `db.init_db` 增 `_ensure_eval_run_columns(engine)` 幂等 ADD COLUMN 迁移
- [ ] 1.3 测试：旧库（无新列）init_db 后能查询/写入新列

## 2. 平台落 trace + retention 收尾
- [ ] 2.1 `build_eval_job` 提前生成 run_slug，向 `evaluate` 传 `run_name/out_dir`
- [ ] 2.2 落库后置 `EvalRun.has_traces`，job 末尾按 `config.run.retention` 调 `prune_outputs`
- [ ] 2.3 测试：平台 run 落 `traces.jsonl.gz` 且 `has_traces=True`；retention 被调用

## 3. 重判 / 续跑 job
- [ ] 3.1 `build_rejudge_job`：源 report.json+traces → `judge_traces` → 新 run + 复制留痕
- [ ] 3.2 `build_resume_job`：源冻结用例 + `resume_dir` → `evaluate` 续跑 → 新 run
- [ ] 3.3 测试：rejudge 一致性（零 adapter 调用、新 run 落库）；resume 复用成功留痕

## 4. REST API + schema
- [ ] 4.1 `POST /runs/{id}/rejudge`、`/resume`（前置校验 + 建新 run + submit）
- [ ] 4.2 `POST /runs/{id}/pin`（toggle pinned + KEEP 哨兵）
- [ ] 4.3 `RunSummaryOut` 透出 `has_traces/pinned/parent_run_id`
- [ ] 4.4 测试：三端点 happy path + 缺留痕 rejudge 返回 400 + pin 写哨兵

## 5. 前端
- [ ] 5.1 `api.ts` 增 `rejudgeRun/resumeRun/setPin` + 类型字段
- [ ] 5.2 `RunDashboardPage` 看板加「重判 / 续跑 / 置顶」按钮，成功后跳新 run

## 6. 收尾
- [ ] 6.1 全量 `pytest` 绿（含平台测试）
- [ ] 6.2 `medeval run --config config.yaml --dry-run`
- [ ] 6.3 `graphify update .` + `openspec validate --strict` + archive
