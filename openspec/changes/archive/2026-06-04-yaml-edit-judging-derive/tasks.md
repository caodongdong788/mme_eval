# Tasks

## 1. TDD 测试先行
- [x] 1.1 `derive_benchmark_from_yaml`：只改判据/改 turns 被忽略、未匹配丢弃、零匹配报错、created_by、源集不变
- [x] 1.2 `GET /runs/{id}/cases-yaml` 按过滤返回可解析 YAML
- [x] 1.3 重判端点透传 `cases_benchmark_id`

## 2. 后端
- [x] 2.1 `_apply_case_overrides`：未匹配跳过 + 零匹配报错
- [x] 2.2 `derive_benchmark_from_yaml`（解析 YAML → 判据覆盖 → 复用 derive）
- [x] 2.3 `POST /api/benchmarks/{id}/derive-yaml`（schema + created_by）
- [x] 2.4 `GET /api/runs/{id}/cases-yaml`（复用 `_filtered_case_rows` + dump）

## 3. 前端
- [x] 3.1 `api.ts`：getRunCasesYaml / deriveBenchmarkFromYaml；移除 deriveBenchmark/CaseLogicOverride
- [x] 3.2 RunDashboard：「编辑判据(YAML)」抽屉
- [x] 3.3 重判对话框：benchmark 下拉（cases_benchmark_id）
- [x] 3.4 CaseDetailPage：移除旧逐条编辑器

## 4. 收尾
- [x] 4.1 全量 pytest 绿
- [x] 4.2 tsc 通过 + `medeval run --dry-run`
- [x] 4.3 `graphify update .` + `openspec validate --strict` + archive
