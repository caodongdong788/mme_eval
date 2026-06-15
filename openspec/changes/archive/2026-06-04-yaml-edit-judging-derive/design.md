# Design

## 数据流

```
看板过滤(level/release/stability/scenario/tag)
  └─ GET /runs/{id}/cases-yaml?<同 /cases 过滤> ──► 命中 sample_id 子集
        └─ 取 run.benchmark 的这些完整用例 → yaml.safe_dump → 文本（预填编辑器）
在线编辑 YAML
  └─ POST /benchmarks/{run.benchmark_id}/derive-yaml {name, yaml_text}
        └─ 解析 → 按 sample_id 只覆盖判据字段（未匹配丢弃）→ create_uploaded_benchmark(新集, created_by)
重判对话框选 benchmark
  └─ POST /runs/{id}/rejudge {cases_benchmark_id: 新集} ──► 冻结 trace 按新判据重判
```

## 后端

### `cases-yaml` 预填（GET /api/runs/{id}/cases-yaml）
复用 `_filtered_case_rows(run_id, …同 /cases 过滤参数)` 取命中行 → 收集 `sample_id` 集合 →
`load_benchmark_cases(run.benchmark)` 取这些完整 `TestCase` → `yaml.safe_dump([model_dump(json)…],
allow_unicode, sort_keys=False)`（剔除 loader 注入的 `case_file`）。返回 `{benchmark_id, count, yaml_text}`。
run 无 benchmark / 过滤后为空 → 400。

### `derive-yaml`（POST /api/benchmarks/{id}/derive-yaml）
body `{name, description?, yaml_text}`。`derive_benchmark_from_yaml`：
1. `yaml.safe_load(yaml_text)`，要求是 list[dict]，否则报错；
2. 每条取 `sample_id` 与判据字段 → 组装 `case_overrides`（只含存在的判据字段）；
3. 调 `derive_benchmark_with_overrides`（已有：复制源集→按 id 覆盖判据→校验→落新集→写 created_by）。

### 合并语义改动（`_apply_case_overrides`）
- 未匹配 `sample_id`：由"抛 `BenchmarkValidationError`"改为**跳过丢弃**；
- 记录命中数，**零命中**抛 `BenchmarkValidationError("没有任何用例 sample_id 匹配源 benchmark")`；
- 仍只覆盖 `_CASE_OVERRIDE_FIELDS`（expected_behavior/hard_gates/rubric/scoring_points），其余字段不动；
- 非法判据仍逐条 `TestCase.model_validate` 报错。

结构化 `POST /benchmarks/{id}/derive` 与其测试保留（同样受益于跳过语义；其测试不依赖未匹配报错）。

## 前端

- `api.ts`：新增 `getRunCasesYaml(id, filters)`、`deriveBenchmarkFromYaml(id, {name, description, yaml_text})`；
  移除 `deriveBenchmark` / `CaseLogicOverride`（不再使用）。
- RunDashboard：「用例结果」区加「编辑判据(YAML)」按钮 → 抽屉（等宽 `Input.TextArea` 预填 + 名称输入 +
  「另存为新 benchmark」）。重判对话框加 benchmark `Select`（`api.listBenchmarks`），提交带 `cases_benchmark_id`。
- CaseDetailPage：移除「编辑判据并另存重判」按钮、编辑 Modal、`openEditor/submitEdit` 及相关 import。

## 测试（TDD）
- `derive_benchmark_from_yaml`：只改判据字段（YAML 改 turns 被忽略）、未匹配 sample_id 丢弃、零匹配报错、
  created_by 落库、源集不变。
- `GET /runs/{id}/cases-yaml`：按过滤返回命中用例 YAML（可被 `load_cases` 解析）。
- 重判端点透传 `cases_benchmark_id`（已部分覆盖，补端点透传断言）。
