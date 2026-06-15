# Design: 可调配置重判 + 派生 benchmark

## 为什么改 config 就能改判分（机制依据）

`build_report` 用传入 `judge_traces` 的 `config` 的 `scoring` 段算四模块分（`config_snapshot.scoring → apply_grading`），LLM judge 用 `config.judges.llm`，HardGate/Rule 从 `case` 现读判据。所以：

- 覆盖 `config.scoring` → 重判即按新权重/阈值重算（甚至不依赖留痕，纯报告层）；
- 覆盖 `config.judges` → 重跑 LLM judge（需留痕）；
- 替换 `case`（改后的判据）→ 重跑 HardGate/Rule（+ rubric 改了则 LLM），需留痕（`n_runs=1` 可用 report.json 代表性 trace 兜底）。

bot 回答（trace）始终冻结 → 分差只反映"被覆盖项"。

## 重判覆盖（临时，不落 config.yaml）

`POST /runs/{id}/rejudge` body（全可选，无 body = 现状）：

```
{ scoring?: {...浅合并到 config.scoring}, judge?: {provider/model/base_url/api_key/...},
  cases_benchmark_id?: <int> }
```

`build_rejudge_job` 在 `judge_traces` 前对 `config` 应用：

- `scoring`：`ScoringCfg.model_validate({**config.scoring.model_dump(), **scoring})`，其中
  `module_max`/`grade_thresholds` 做嵌套浅合并（允许只写要调的维度）。
- `judge`：复用既有 `_apply_judge_overrides`（合并进 `config.judges.llm/scoring_point`）。
- `cases_benchmark_id`：加载该 benchmark 的用例，按 `sample_id` 把冻结用例替换为"改后的 case"
  （找不到则保留冻结 case，源 run 为子集时按其 sample_id 子集替换），trace 仍按原顺序配对。

覆盖只作用于本次重判产出的新 run；判分模型公共参数记入新 run 的 `judge_overrides`，
完整 scoring 进 `config_snapshot`，可审计。

## 派生 benchmark（改 case 判据，不动原 benchmark）

`POST /benchmarks/{id}/derive` body：`{ name, description?, case_overrides: [{sample_id,
expected_behavior?, hard_gates?, rubric?}] }`。`derive_benchmark_with_overrides`：

1. `load_benchmark_cases(源 bm)` → `{sample_id: TestCase}`；
2. 对每条 override 取该 case 的 `model_dump(mode="json")`，覆盖给定字段，`TestCase.model_validate`
   逐条校验（非法即拒绝）；
3. 全量用例 `yaml.safe_dump` → 复用 `create_uploaded_benchmark`（再过 `loader` 校验 + 唯一名 +
   写 `created_by`）落为新的 uploaded benchmark。

源 benchmark（含 builtin 内置用例集）**只读不改**。前端流程：编辑判据 → derive 新 bm →
`rejudge(cases_benchmark_id=新bm)` → 跳新 run。

## benchmark 上传人

`Benchmark.created_by`（既有列，String(100)）在 upload / derive 时写入当前登录用户显示名
（`get_current_user_optional().name`；未登录 dev 态写空/`本地`）。`BenchmarkOut` 透出
`created_by`，前端列表新增「上传人」列。无新增 DB 列、无需迁移。

## 安全/边界

- `judge.api_key` 仅运行期用，不入库（沿用 `JudgeOverride.public_dict`）。
- 派生 benchmark 名唯一性由 `create_uploaded_benchmark` 保证（重名 422）。
- 重判前置校验不变：源 run 非成功、或 `n_runs>1` 但留痕已清理 → 400。
- `cases_benchmark_id` 指向不存在 benchmark → 400。
