# eval-platform-service Specification (delta)

## ADDED Requirements

### Requirement: 平台评测落会话留痕与存储治理

平台发起的评测 SHALL 复用内核 `evaluate(run_name, out_dir)` 落盘会话留痕：任务在调用前
提前生成 run_slug 并以 `outputs/<slug>` 为产物目录，使网页评测与 CLI 一样落
`traces.jsonl.gz`。落库时系统 MUST 依据该目录是否存在 `traces.jsonl.gz` 置
`eval_run.has_traces`。评测任务完成后系统 MUST 按 `config.run.retention` 自动清理历史
run 的胖产物（traces / xlsx），并永久保留 `report.json` 与数据库数据；清理失败 MUST NOT
使评测整体失败。

#### Scenario: 网页评测落 trace 并标记

- **WHEN** 用户在平台发起一次评测且 `config.run.persist_traces` 为真
- **THEN** 系统在 `outputs/<slug>/traces.jsonl.gz` 落会话留痕，并将该 run 的
  `eval_run.has_traces` 置为真

#### Scenario: 评测收尾自动治理存储

- **WHEN** 一次平台评测完成落库后
- **THEN** 系统按 `config.run.retention` 调用清理，删除超出保留范围的历史 run 胖产物，
  但 `report.json`、数据库记录与被置顶（含 `KEEP` 哨兵）的 run MUST 保留

### Requirement: 平台离线重判

系统 SHALL 提供 `POST /api/runs/{run_id}/rejudge`：对源 run 的冻结用例（取自
`report.json`）与冻结会话留痕（取自 `traces.jsonl.gz`）**仅重跑判分**（零被测 bot 调用），
产出一个 `parent_run_id` 指向源 run 的**新 run**，默认与源 run 对比以凸显判分逻辑变化。
源 run 非成功、或 `n_runs>1` 但留痕已被清理无法重做 majority 时，系统 MUST 返回 400 及
可读原因；不存在的 run MUST 返回 404。

#### Scenario: 重判产出新 run 且不调用 bot

- **WHEN** 用户对一个已落 trace 的成功 run 发起重判
- **THEN** 系统新建一行 `eval_run`（`parent_run_id` 指向源 run）并仅以冻结留痕重跑判分落库，
  执行过程 MUST NOT 调用被测 bot

#### Scenario: 留痕缺失无法重判

- **WHEN** 源 run `n_runs>1` 且其 `traces.jsonl.gz` 已被存储治理清理
- **THEN** 系统 MUST 返回 400 并提示留痕已清理、无法重做 majority voting

### Requirement: 平台断点续跑

系统 SHALL 提供 `POST /api/runs/{run_id}/resume`：以源 run 的冻结用例与成功会话留痕续跑，
仅对失败 / 缺失的用例重新调用被测 bot，产出 `parent_run_id` 指向源 run 的**新 run**。当源
run 的 adapter 指纹与当前配置不一致时，系统 MUST 拒绝复用旧留痕（由内核续跑逻辑保证），
避免把不同 bot 的结果混入同一次评测。

#### Scenario: 续跑复用成功留痕

- **WHEN** 用户对一个部分用例失败的 run 发起续跑
- **THEN** 系统新建 run，复用源 run 中成功用例的留痕、仅对失败用例重调 bot，并落库为新 run

### Requirement: 评测 run 置顶保护

系统 SHALL 提供 `POST /api/runs/{run_id}/pin` 切换 `eval_run.pinned`，并在该 run 产物目录
创建或删除 `KEEP` 哨兵文件，使 CLI 与平台的存储治理 MUST 豁免被置顶 run 的胖产物。

#### Scenario: 置顶后免于清理

- **WHEN** 用户置顶一个 run
- **THEN** 系统将其 `pinned` 置真并在产物目录写入 `KEEP` 哨兵，后续存储治理 MUST NOT 删除
  该 run 的 `traces.jsonl.gz` 与 `transcripts.xlsx`

### Requirement: 平台数据库附加列幂等迁移

系统 SHALL 在 `init_db` 建表后对 `eval_run` 执行幂等的附加列迁移（`has_traces` /
`pinned` / `parent_run_id`）：对已存在但缺这些列的旧库 MUST 通过 `ALTER TABLE ADD COLUMN`
补齐，对全新库为空操作；迁移 MUST 可重复执行而不报错。

#### Scenario: 旧库自动补列

- **WHEN** 一个在本次变更前创建、`eval_run` 无新列的数据库启动平台
- **THEN** 系统自动为 `eval_run` 补齐 `has_traces` / `pinned` / `parent_run_id` 列，
  且重复启动不报错、不丢数据
