# Tasks

## 1. 续跑可恢复中断 run（后端）

- [x] 1.1 `server/eval_job.py`：新增 `_write_run_plan(out_dir, cases, n_runs)` / `_read_run_plan(out_dir)`，`build_eval_job` 与 `build_resume_job` 在算定 `out_dir` 后、`evaluate` 前落 `plan.json`
- [x] 1.2 `server/eval_job.py`：新增 `_resume_cases_and_traces(...)`——有 `report.json` 走原 `_frozen_cases_and_traces`；否则读 partial 留痕 + 从源 benchmark（按 plan.json 过滤/排序，无 plan 回退全量）重建用例集；`build_resume_job` 改用之
- [x] 1.3 `server/routers/runs.py`：`resume_run` 闸门改为"有可复用留痕（gz 或 partial）"；二者皆无→400；无 report 且无 benchmark→400
- [x] 1.4 TDD：`tests/server/test_resume_interrupted.py` 覆盖（重建用例集 / 端点接受中断 run / 无留痕拒绝 / plan.json 落盘）

## 2. 列表指南匹配率带计数

- [x] 2.1 `server/routers/runs.py`：新增 `_guideline_counts(row)`（从 detail_json 派生命中/总数），在 `_filtered_case_rows` 标注 `guideline_matched`/`guideline_total`
- [x] 2.2 `server/schemas.py`：`CaseRowOut` 新增 `guideline_matched`/`guideline_total`
- [x] 2.3 `frontend/src/api.ts`：`CaseRow` 新增两字段；`RunDashboardPage.tsx` 列渲染 `X%（命中/总数）`
- [x] 2.4 TDD：`tests/server/test_guideline_count_rows.py` 验证列表派生计数

## 3. 验证与归档

- [x] 3.1 `pytest` 全量绿
- [x] 3.2 `medeval run --config config.yaml --dry-run` 通过
- [x] 3.3 `graphify update .` 刷新图谱
- [x] 3.4 文档同步（`server/README.md` 续跑/列表说明）
- [x] 3.5 `openspec validate --strict` 通过后归档
