# Design — 推理产物落盘 + 离线重判 + 断点续跑 + 存储治理

## 关键决策

### 1. 落盘格式：gzip + jsonl（零新依赖）
`outputs/<run>/traces.jsonl.gz`。首行 meta，其后每行一条 `(sample_id, case_index, run_idx, trace)` 记录。选 gzip 而非 zstd 以**不引入第三方依赖**；对话文本 + 重复 JSON 结构 gzip 压缩比通常 5–10×。

### 2. store_raw 瘦身：默认 on_error
`ConversationTrace.raw_responses`（bot 原始响应体）是体积大头，但离线重判只读 `messages` 文本。`run.store_raw` 三档：
- `never`：永不存 raw（最省）。
- `on_error`（默认）：仅 `trace.error` 非空的留全量 raw（排障需要），成功轮次清空。
- `always`：全量留（排障/审计最强，最占）。
裁剪在**写入时**发生，partial 文件也已是瘦身后的，省盘贯穿全程。

### 3. 增量流式落盘（崩溃也留得下）
run 阶段每完成一个 `(case, run_idx)` 即追加写 `traces.partial.jsonl`（未压缩、可 append）。run 阶段整体结束后 `finalize_traces` 压缩成 `traces.jsonl.gz` 并删 partial。
- 为支持流式，CLI 在**开跑前**生成 run slug 并算出 `out_dir`，作为可选 `out_dir`/`run_name` 形参传入 `evaluate()`；`evaluate()` 用同一 slug 给 `build_report`，保证 `report.run_name == out_dir.name`。
- `evaluate()` 不传 `out_dir`（平台 / SDK / 测试）时**不落盘**，行为与现状逐字段一致。

### 4. run/judge 解耦：`run_traces` + `judge_traces`
把 `evaluate()` 内联两段抽成可复用函数：
- `run_traces`：唯一 adapter 副作用，产出 `list[list[ConversationTrace]]`。
- `judge_traces`：纯判分（判分→fold→llm→sp→软分→build_report），**零 adapter**。
`rejudge` 命令直接复用 `judge_traces`，是离线重判能落地的根本前提。

### 5. 进度 plan 仍开跑前一次性声明
现有 `test_service.py` 要求 evaluate 开跑前 `plan_phases` 一次性声明全 plan（前端算全局单调进度）。重构后由 `evaluate()` 编排层拼 `run_phase_plan + judge_phase_plan` 一次性声明；`judge_traces` 单独被 rejudge 调用时自行声明 judge-only plan。

### 6. 断点续跑：复用成功留痕 + adapter 指纹校验
`run --resume <prev_dir>` 读 `prev_dir` 的留痕，构造 `resume_index[(sample_id, run_idx)] -> trace`，**只保留 error 为空的成功留痕**；executor 命中则复用、缺失/失败者重跑。
- **安全闸**：meta 里存 adapter 指纹（adapter type + 关键配置的 sha1，排除 api_key/base_url 等敏感/易变项？——为避免误用，指纹取 `adapter.type` + `system_prompt` + `model`）。当前 config 指纹与 prev 不一致 → **拒绝复用并报错**，绝不拿错 bot 的旧 trace 混入。
- resume 仅支持 `local` 后端；`executor=ray` + resume → 报清晰错误（ray worker 批量跑 N-runs，逐 run 跳过需另设计，本期非目标）。

### 7. rejudge 用「冻结用例 + 冻结留痕」
- 冻结用例：从 `prev_dir/report.json` 的 `results[i].case` 取（已是完整 `TestCase`），保证用例不随 `cases/` 后续改动而变。
- 冻结留痕：从 `traces.jsonl.gz` 按 `sample_id` 取全部 N-runs，重建 `per_case_traces` 后喂 `judge_traces`。
- 回退：无 `traces.jsonl.gz` 但 `n_runs==1` 时，用 `report.json` 的代表性 trace 兜底重判；`n_runs>1` 且无 traces → 报错（代表性 trace 不足以重做 voting）。
- 输出到**新** run 目录（保留溯源），默认与 prev run diff。

### 8. retention：拆「长期可 diff」与「短期可重判」
- `report.json`（瘦底座）**永久保留** → 趋势/diff 不断链。
- 胖产物（`traces.jsonl.gz`/`transcripts.xlsx`/残留 `traces.partial.jsonl`）由 retention 滚动清理：超 `keep_last`（按 mtime）或超 `ttl_days` 的 run 删胖产物。
- `keep_tagged=true` 时，run 目录含 `KEEP` sentinel 文件者永久豁免（baseline / 发版门禁 run 手动 `touch outputs/<run>/KEEP` 即保）。
- run 收尾自动 prune；`medeval prune` 可手动触发（含 `--dry-run` 预览）。
- 效果：稳态磁盘 ≈ `keep_last × 单 run 压缩后大小`，不随评测次数线性爆炸。

## 兼容性

- 新增配置字段默认值=现状语义；`evaluate()` 新增形参全可选；不传时（平台/SDK/测试）逐字段行为不变。
- 不触碰 `TestCase`/`BaseJudge`/`FailureTag`/`hard_gate.py` 启发式 → 无需 `verify-heuristics`、judge fingerprints 不变。
