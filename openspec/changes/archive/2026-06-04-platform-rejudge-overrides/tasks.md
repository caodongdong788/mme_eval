# Tasks

## 1. schema
- [x] 1.1 `RejudgeRequest`（scoring?/judge?/cases_benchmark_id?）、`CaseLogicOverride`、`DeriveBenchmarkRequest`
- [x] 1.2 `BenchmarkOut` 增 `created_by`

## 2. 后端：重判覆盖
- [x] 2.1 `_apply_scoring_override`（嵌套浅合并 → ScoringCfg 校验）
- [x] 2.2 `build_rejudge_job` 接收并应用 scoring/judge/cases_benchmark_id
- [x] 2.3 `POST /runs/{id}/rejudge` 读 body、校验 cases_benchmark_id 存在、传入 job
- [x] 2.4 测试：scoring 覆盖改分、judge 覆盖、cases_benchmark_id 用改后判据重判

## 3. 后端：派生 benchmark + 上传人
- [x] 3.1 `derive_benchmark_with_overrides`（复制+套用+校验+落盘，写 created_by）
- [x] 3.2 `POST /benchmarks/{id}/derive`（current_user → created_by）
- [x] 3.3 upload 端点写 created_by；`BenchmarkOut` 透出
- [x] 3.4 测试：派生不动源 bm、非法 override 拒绝、created_by 落库与透出

## 4. 前端
- [x] 4.1 `api.ts`：rejudge 带 body、deriveBenchmark、Benchmark.created_by 类型
- [x] 4.2 RunDashboard：重判弹框（权重/阈值 + judge 模型）
- [x] 4.3 CaseDetail：判据编辑器（hard_gates + expected_behavior）→ 另存新 benchmark + 重判
- [x] 4.4 Benchmarks：上传人列

## 5. 收尾
- [x] 5.1 全量 pytest 绿（含平台测试）
- [x] 5.2 frontend tsc 通过 + `medeval run --dry-run`
- [x] 5.3 `graphify update .` + `openspec validate --strict` + archive
