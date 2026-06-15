# Design: 平台落 trace + 重判/续跑 + 存储治理

## 复用内核，不改判分核

平台只编排，不新增判分逻辑：

- 落 trace / 续跑：复用 `medeval.service.evaluate(run_name, out_dir, resume_dir)`。
- 离线重判：复用 `medeval.service.judge_traces(...)` + `trace_store.read_traces / write_traces`。
- 清理：复用 `medeval.retention.prune_outputs(...)` 与 `KEEP` 哨兵。
- run 目录名：复用 `medeval.run_slug.make_run_slug`。

## run_slug 提前生成（解决先有目录名才能落盘的鸡生蛋）

`build_eval_job` 在调 `evaluate()` **前**用 `make_run_slug(config.run.name)` 生成 `run_slug`，
`out_dir = settings.outputs_dir / run_slug`，把 `run_name=run_slug, out_dir=out_dir` 传给
`evaluate()`，使 `report.run_name` 与落盘目录一致（与 CLI 同口径）。落库后置
`EvalRun.has_traces = (out_dir / "traces.jsonl.gz").exists()`。

## 重判 / 续跑都产出"新 run"（不可变审计）

源 run 不被覆盖。两者都：新建一行 `EvalRun(status=pending, parent_run_id=<源 id>)` →
后台 job 从**源 run 的 `report.json`（冻结用例）**与 **`traces.jsonl.gz`（冻结留痕）**重建输入：

- **rejudge**：`judge_traces(cases, per_case_traces, judges, adjudicator, run_name=new_slug)`，
  零 adapter 调用；产物默认与源 run 的 `report.json` 对比（凸显判分逻辑变化）；
  同时 `write_traces` 把冻结留痕复制到新目录，使新 run 仍可被再次重判。
- **resume**：`evaluate(cases, ..., out_dir=new_out_dir, resume_dir=<源 out_dir>)`，
  复用源 run 成功留痕、仅对失败/缺失用例重调 bot；adapter 指纹不一致 `evaluate` 内部即拒绝。

判分模型 / bot 覆盖沿用源 run 的 `judge_overrides / adapter_overrides`（保持同一 judge/bot 身份，
只让 `config.yaml` 的 scoring 口径变化成为单变量）。`config.run.repeat` 取源 run 的 `n_runs`。

## 前置校验（端点层，避免造无效 run）

- rejudge：源 run 必须 `status==success` 且有 `report.json`；若 `n_runs>1` 但缺
  `traces.jsonl.gz`（已被 retention 清理）→ 返回 400，提示留痕已清理无法重做 majority。
- resume：源 run 必须有 `report.json`（拿冻结用例）；缺 `traces.jsonl.gz` 则等价全量重跑，允许。
- 名称唯一：新 run 名 = `f"{源名} · 重判/续跑 {MMDD-HHMMSS}"`，时间戳后缀避免与既有 run 撞名。

## DB 迁移（SQLite 友好、幂等）

`EvalRun` 新增 `has_traces: bool=False`、`pinned: bool=False(index)`、`parent_run_id: int|None`。
`create_all` 不会给已存在表加列，故 `init_db` 在建表后调 `_ensure_eval_run_columns(engine)`：
用 `inspect(engine)` 读现有列名，对缺失列发 `ALTER TABLE eval_run ADD COLUMN ...`（带默认值）。
SQLite / Postgres 的简单 ADD COLUMN 均支持；幂等、对全新库为空操作。

## 置顶（pin）= DB 标记 + 文件哨兵双写

`POST /api/runs/{id}/pin` 切换 `EvalRun.pinned`，并在 `out_dir` 创建/删除 `KEEP` 文件，
使 CLI（`medeval prune`）与平台 retention 共用同一豁免信号，避免置顶 run 的胖产物被清。

## retention 收尾

评测 job 末尾 `try/except` 调 `prune_outputs(outputs_dir, keep_last, ttl_days, keep_tagged)`
（取 `config.run.retention`）。清理只删胖产物、保留 `report.json` 与 DB；被清 run 的
`has_traces` 不回写（仍为 True），rejudge/resume 端点以"文件是否存在"为准做前置校验并友好报错。
