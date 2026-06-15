# Design

## 1. 判据覆盖保存（功能 1）

复用现有另存链路 `derive_benchmark_from_yaml → derive_benchmark_with_overrides → _apply_case_overrides`：

- `_apply_case_overrides` 已是"复制源集**全部**用例、按 `sample_id` 合并判据字段、未匹配 sample_id 丢弃、零匹配抛错、源对象不改"——即源集里不在当前过滤的用例**原样保留**，无数据丢失风险。
- 新增 `overwrite_benchmark_from_yaml(session, target, yaml_text)`：解析 YAML→overrides（同 `derive_benchmark_from_yaml`），用 `_apply_case_overrides` 得到合并后的完整用例列表，再**写回 `target` 的存储文件**（沿用 `replace_uploaded_benchmark` 的落盘/校验/`case_count` 更新路径），而非新建记录。
- 内置（`source=="builtin"`）MUST 抛 `BenchmarkValidationError` / 路由 400。
- 端点：`POST /api/benchmarks/{id}/overwrite-yaml`，body `OverwriteBenchmarkYamlRequest{ yaml_text }`，返回 `BenchmarkOut`。

## 2. 重判优化（功能 2）

### 2a. judge 下拉
`RejudgeRequest` 增 `judge_model_id: Optional[int]`。`rejudge_run` 解析逻辑直接复用 `create_run`（runs.py L84–98）：据 `JudgeModelConfig` 构建 `JudgeOverride`（含 Key，仅运行期注入、`public_dict` 入库剔除 key）。`judge_model_id` 不存在→404。前端不再传手填 `judge`（schema 仍保留 `judge` 字段做 API 向后兼容）。

### 2b/2c. 只重判上线失败 + 合并重算（仍产新 run）
`RejudgeRequest` 增 `only_release_failed: bool=False`，透传到 `build_rejudge_job(only_release_failed=...)`。

job 内（`only_release_failed=True` 时）：

1. 载入源 `report.json` → `RunReport.model_validate_json`，取 `source.results`（已折叠、带 `release_passed`）。
2. `failed_ids = {r.case.sample_id for r in source.results if not r.release_passed}`。
3. 按 `failed_ids` 取**失败用例子集**的 `cases` 与 `per_case_traces`（保序）。
4. 对子集调 `judge_traces(...)` → 取其 `.results`（失败用例的新折叠结果）。
5. **合并**：按源 run 用例顺序，失败用例用新结果、其余用 `source.results` 原结果，得 `merged_results`。
6. `build_report(run_name=new_slug, results=merged_results, adapter_type, config_snapshot, started_at, n_runs)` 重算整体分数/通过率/分布/CI。
7. 落库 + 复制**全部**冻结留痕（非仅子集）到新目录，使新 run 仍可再次被全量/部分重判。

校验：端点处 `only_release_failed=True` 但源 run 无 `release_passed=false` 用例 → 400「无上线失败用例可重判」。

### 已知特性（非缺陷，文档化）
- 合并报告的 `judge_fingerprints` 为**混合**：通过用例沿用源判分指纹、失败用例用新判分指纹。这是"只重判失败"的固有语义，报告 diff 仍可区分。`only_release_failed=False`（默认全量）不受影响。

## 3. 不变量
- 重判**零 bot 调用**、源 run **不可变**、新 run `parent_run_id` 指向源、默认与源 diff——全部保持。
- 判分内核只复用 `judge_traces` / `build_report`，不改核心 schema/judge。
