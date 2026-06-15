## 1. Phase 1 — config 字段

- [x] 1.1 `medeval/config.py` 新增 `RetentionCfg`（`enabled: bool = True`、`keep_last: int = 20`（ge=0，0=全留）、`ttl_days: int | None = None`、`keep_tagged: bool = True`）
- [x] 1.2 `RunCfg` 增 `store_raw: Literal["never","on_error","always"] = "on_error"`、`persist_traces: bool = True`、`retention: RetentionCfg`
- [x] 1.3 `config.yaml` 增注释样例（值=默认，行为不变）

## 2. Phase 2 — trace 落盘模块（persistence）

- [x] 2.1 新增 `medeval/trace_store.py`：`trim_raw_responses(trace, store_raw)`（never→清空 / on_error→仅 error 保留 / always→不动）
- [x] 2.2 `PartialTraceWriter`：run 阶段增量写 `traces.partial.jsonl`（meta 行含 adapter_fingerprint/store_raw/n_runs/schema + 每 (sample_id, run_idx) 一行）
- [x] 2.3 `finalize_traces(out_dir)`：partial → `traces.jsonl.gz`（gzip），删 partial
- [x] 2.4 `read_traces(run_dir)`：返回 meta + `by_key[(sample_id, run_idx)] -> ConversationTrace`；兼容 `.gz` 与残留 `.partial.jsonl`
- [x] 2.5 `per_case_traces_for(cases, by_key, n_runs)`：按给定用例顺序重建 `list[list[ConversationTrace]]`（rejudge 用）

## 3. Phase 3 — service 抽函数 + 落盘/续跑编排

- [x] 3.1 `medeval/service.py` 抽 `run_traces(config, cases, adapter, *, progress, out_dir=None, resume_dir=None)`：仅 run 阶段；out_dir+persist 时增量落盘；resume_dir 时加载成功留痕做跳过
- [x] 3.2 抽 `judge_traces(config, cases, per_case_traces, judges, adjudicator, *, progress, started_at=None)`：判分→fold→llm→sp→软分→`build_report`（纯判分、零 adapter）
- [x] 3.3 `evaluate()` 改为 `run_traces` + `judge_traces` 编排；新增可选 `run_name`/`out_dir`/`resume_dir` 形参（缺省=现状逐字段不变）；run 阶段后 `finalize_traces`
- [x] 3.4 `judge_phase_plan`/`run_phase_plan` 辅助：evaluate 仍开跑前一次性声明完整 plan（单调进度不回退）

## 4. Phase 4 — executor resume

- [x] 4.1 `medeval/runner/executor.py` `run_cases` 增可选 `resume_index: dict[(str,int), ConversationTrace] | None`：命中且无 error 的 (sample_id, run_idx) 直接复用并照常 `on_progress`
- [x] 4.2 `executor=ray` 且传入 resume → 由 service 层抛清晰错误（resume 仅支持 local）

## 5. Phase 5 — retention/prune

- [x] 5.1 新增 `medeval/retention.py`：`prune_outputs(outputs_dir, *, keep_last, ttl_days, keep_tagged, dry_run)`——按 mtime 排序，超 keep_last 或超 ttl 的 run 删胖产物（`traces.jsonl.gz`/`transcripts.xlsx`/`traces.partial.jsonl`），保 `report.json`，含 `KEEP` sentinel 的目录豁免
- [x] 5.2 `run` 收尾在 `retention.enabled` 时自动调用 prune（dry-run 命令早返回不触发）

## 6. Phase 6 — CLI 入口

- [x] 6.1 `medeval/cli.py` `run`：开跑前生成 run slug 并算出 `out_dir`，传入 `evaluate`；新增 `--resume <run_dir>` 选项；收尾触发 retention
- [x] 6.2 新增 `medeval rejudge <run_dir>`：读 `report.json`(冻结用例) + `read_traces`(冻结留痕) → `judge_traces` → 写新 run 目录，默认与原 run diff；缺 traces 且 n_runs==1 时回退用 report.json 代表性 trace，否则报清晰错误
- [x] 6.3 新增 `medeval prune`：手动触发 retention（`--keep-last`/`--ttl-days`/`--dry-run`）

## 7. 测试（TDD，先写后实现）

- [x] 7.1 `trace_store` round-trip：写→读 `ConversationTrace` 逐字段一致（含 messages/latencies/error）
- [x] 7.2 `store_raw` 三档：never 清空 raw、on_error 仅 error 保留、always 全留
- [x] 7.3 rejudge 一致性：冻结 trace 上重判，judge verdict / 综合分与原 run 一致（同 config）
- [x] 7.4 resume：注入部分成功留痕 → 命中的 (sample_id, run_idx) 不再调 adapter、缺失者重跑；adapter 指纹不匹配拒绝
- [x] 7.5 retention：keep_last 删胖留瘦、`KEEP` 豁免、`report.json` 永久保留
- [x] 7.6 回归：evaluate 不传新形参时产物/进度 phase 与现状一致（不破 `test_service.py`）

## 8. 收尾

- [x] 8.1 `pytest`（含 `-m golden`）全绿
- [x] 8.2 `medeval run --config config.yaml --dry-run` 通过（71 条用例 + 新配置字段校验）
- [x] 8.3 `graphify update .` 刷新图谱
- [x] 8.4 `openspec validate --strict` 通过后归档
