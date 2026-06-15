# eval-platform-service Specification (delta)

## MODIFIED Requirements

### Requirement: 平台断点续跑

系统 SHALL 提供 `POST /api/runs/{run_id}/resume`：复用源 run 的成功会话留痕续跑，仅对失败 / 缺失的用例重新调用被测 bot，产出 `parent_run_id` 指向源 run 的**新 run**。当源 run 的 adapter 指纹与当前配置不一致时，系统 MUST 拒绝复用旧留痕（由内核续跑逻辑保证），避免把不同 bot 的结果混入同一次评测。

可续跑判据 MUST 为「源 run 目录存在可复用留痕」——即 `traces.jsonl.gz` **或** `traces.partial.jsonl` 至少其一存在；二者皆无（从未落盘或已被存储治理清理）时 MUST 返回 400 及可读原因。运行中 / 等待中的 run MUST 拒绝续跑；不存在的 run MUST 返回 404。

为支持**被服务重启 / 崩溃中断**（从未写出 `report.json`）的 run 续跑，系统 MUST 在每次评测启动时落一份 `plan.json`（记录过滤后的实际用例 `sample_ids` 与 `n_runs`）。续跑重建用例集时：源 run 有 `report.json` 则取其冻结用例；否则 MUST 从源 run 关联的 benchmark 重建用例集，并按 `plan.json` 的 `sample_ids` 过滤与排序（缺 `plan.json` 时回退该 benchmark 全量），再以 `traces.partial.jsonl` 中成功留痕续跑。源 run 无 `report.json` 且未关联 benchmark（无法重建用例集）时 MUST 返回 400。

#### Scenario: 续跑复用成功留痕

- **WHEN** 用户对一个部分用例失败的 run 发起续跑
- **THEN** 系统新建 run，复用源 run 中成功用例的留痕、仅对失败用例重调 bot，并落库为新 run

#### Scenario: 续跑被服务重启中断的 run

- **WHEN** 一个 run 因服务重启被回收为 `failed`、从未写出 `report.json`，但其目录仍存 `traces.partial.jsonl`
- **THEN** 系统 MUST 接受续跑请求，从源 run 的 benchmark（按 `plan.json` 过滤）重建用例集，复用 partial 留痕中成功的用例、仅对其余用例重调 bot

#### Scenario: 无可复用留痕拒绝续跑

- **WHEN** 源 run 目录中 `traces.jsonl.gz` 与 `traces.partial.jsonl` 均不存在
- **THEN** 系统 MUST 返回 400 并提示无可复用留痕、无法续跑
