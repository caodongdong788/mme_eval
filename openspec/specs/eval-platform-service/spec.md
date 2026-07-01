# eval-platform-service Specification

## Purpose
MME · Agent 评测平台的后端服务能力：在判分内核 medeval 之上提供评测结果持久化、benchmark 库管理、评测任务异步调度与状态/进度跟踪、可配置判分模型的发起评测、run 名称唯一性与删除、对话流水以登录用户身份导出到飞书，以及覆盖上述的 REST API。
## Requirements
### Requirement: 评测结果持久化

系统 SHALL 将每次评测的 `RunReport` 持久化到关系数据库：run 级汇总与可聚合维度存为 `eval_run` / `case_result` 的标量列，单条用例完整明细（对话、verdict、扣分原因、命中关键词、得分点）存为 JSON 列。数据库连接 MUST 经 `MEDEVAL_DATABASE_URL` 配置化，默认 SQLite，可切换 PostgreSQL。

#### Scenario: 评测完成后落库

- **WHEN** 一次评测执行完成并产出 `RunReport`
- **THEN** 系统在 `eval_run` 写入一行汇总（total/passed/pass_rate/hard_gate_failed/grading 等），并在 `case_result` 为每条用例写入标量列与 `detail_json`
- **AND** 既写数据库、也按现有规则写 `outputs/<slug>/report.json`（双写兼容）

#### Scenario: 读回与落库一致

- **WHEN** 从数据库读回某次 run 的用例明细
- **THEN** 其内容 MUST 与原始 `CaseResult` 一致（通过率轴 `release_passed/gate_passed/hard_gate_passed`、分数、稳定性、verdict 均无损还原）

### Requirement: benchmark 库管理

系统 SHALL 提供 benchmark 库：支持上传与 `cases/` 同格式的 YAML 用例集，上传时 MUST 用现有 `loader` 校验，校验失败 MUST 拒绝并返回错误；合法 benchmark 保存元数据（name/version/case_count/source）供重复选用。内置 `cases/breast_cancer` MUST 作为 `source=builtin` 的 benchmark 可见。

当上传请求的 `source=online` 时，系统 MUST 复用同一个 `POST /api/benchmarks` 入口支持两类输入：JSONL 文件或 `source_url` 飞书 Base URL。若提供 `source_url`，系统 MUST 使用当前登录用户的 `user_access_token` 调用飞书多维表格 OpenAPI 读取记录；若未提供 `source_url`，系统 MUST 沿用线上 JSONL 文件解析。飞书 Base 记录转 benchmark 时 MUST 把每条记录的每轮用户输入与 Cx 输出按顺序写入 `turns`，不得只保留第一轮。

#### Scenario: 上传合法 benchmark

- **WHEN** 用户上传一个合法的用例 YAML 文件
- **THEN** 系统校验通过后保存用例与元数据，并在 benchmark 列表中可见、可在发起评测时选用

#### Scenario: 上传非法 benchmark 被拒绝

- **WHEN** 用户上传的 YAML 不符合 `TestCase` schema
- **THEN** 系统 MUST 拒绝保存并返回可读的校验错误信息

#### Scenario: 从飞书 Base URL 导入线上 benchmark

- **WHEN** 用户提交 `source=online`、benchmark 名称与飞书 Base URL
- **THEN** 系统 MUST 读取 URL 指定的数据表/视图，将每条记录转换为一个 `source=online` case 并保存为 benchmark
- **AND** 每个 case 的 `turns` MUST 按「第一轮用户输入 / 第一轮Cx输出」到「第四轮用户输入 / 第四轮Cx输出」的非空轮次完整落盘

#### Scenario: Base URL 导入权限不足

- **WHEN** 当前用户未登录、token 失效或缺少读取该 Base 的权限
- **THEN** 系统 MUST 拒绝导入并返回可读错误，不得创建空 benchmark

### Requirement: 评测任务调度与状态跟踪

系统 SHALL 通过 `JobRunner` 抽象异步执行评测：发起后立即创建 `eval_run(status=pending)` 并返回 run id，后台执行时状态流转 `pending → running → success/failed`，失败 MUST 记录用户可读的 `error_msg`（完整异常仅进服务端日志）。多个评测任务并发执行 MUST 受并发上限约束。运行进度 SHALL 可被查询，且其完成百分比 MUST 为「跨全部阶段的全局累计值」、随评测推进**单调不回退**（一次评测含多个顺序阶段时，切换阶段 MUST NOT 使百分比下降）。

#### Scenario: 评测失败记录原因

- **WHEN** 后台执行过程中评测或 Pairwise 对比抛出未捕获异常
- **THEN** 对应记录的 `status` MUST 置为 `failed` 且 `error_msg` MUST 为固定用户可读短句，MUST NOT 包含 Python 堆栈或内部异常原文

### Requirement: 发起评测可配置评测打分模型

系统 SHALL 允许在发起评测时配置评测打分模型（LLM-as-Judge 与 scoring_point 的 provider / model / base_url / api_key），这些参数 MUST 合并进评测配置后再装配 judge；判分逻辑本身 MUST 不被修改。被测 bot 默认沿用服务器 `config.yaml` 的 adapter，并允许可选覆盖。api_key 等敏感参数 MUST NOT 以明文持久化入库。

#### Scenario: 指定打分模型发起评测

- **WHEN** 用户发起评测并指定 judge 的 model 与 base_url
- **THEN** 系统用该打分模型装配 judge 执行评测，`eval_run.judge_overrides` 记录非敏感参数，api_key 不入库

### Requirement: 评测平台 REST API

系统 SHALL 暴露 REST API 覆盖：benchmark 的上传/列表/详情/用例清单/删除；评测的发起/列表/详情/进度/用例结果列表（支持按维度筛选）/单条用例明细/两次 run 对比；以及跨 run 趋势数据与用例库浏览。

#### Scenario: 下钻单条用例明细

- **WHEN** 客户端请求某次 run 中某 `sample_id` 的明细
- **THEN** 系统返回该用例完整对话流水、各 judge verdict、扣分原因、命中关键词、per-run 稳定性与得分点

#### Scenario: 两次 run 对比

- **WHEN** 客户端请求将某次 run 与另一历史 run 对比
- **THEN** 系统返回两者在通过率、各维度与判分指纹上的差异

### Requirement: 对话流水导出以登录用户身份上传飞书

系统 SHALL 在导出对话流水（`POST /api/runs/{run_id}/export-transcripts`）时，使用**当前
登录用户的 `user_access_token`** 直接调用飞书 OpenAPI（`drive/v1/files/upload_all` →
`drive/v1/import_tasks` → 轮询 `import_tasks/{ticket}`）将 xlsx 导入为在线表格，不再依赖
`lark-cli` 的共享身份。目标文件夹 `mount_key` 取调用方传入的 token，空值 MUST 表示个人
空间根目录。上传或导入失败时系统 MUST 返回 502 及可操作的失败原因（权限/文件夹/重登）。

#### Scenario: 登录用户导出成功

- **WHEN** 已登录用户按过滤条件请求导出对话流水
- **THEN** 系统以该用户飞书 token 上传并导入为在线表格，返回飞书表格 URL、用例数与文件名

#### Scenario: 传入文件夹 token

- **WHEN** 用户在导出时传入飞书文件夹 token
- **THEN** 系统将表格导入到该文件夹（需该用户对其有写权限）；传空则导入到个人根目录

#### Scenario: 导入失败返回可操作原因

- **WHEN** 上传或导入任务失败（无权限/文件夹不可写/token 失效）
- **THEN** 系统返回 502 并给出明确原因与下一步建议

### Requirement: 发起评测名称唯一性

系统 SHALL 在发起评测时校验最终 run 名称（用户填写的 `run_name`，缺省时为 benchmark 名）
的唯一性；若与已存在的 run 重名，系统 MUST 拒绝创建并返回 409 及可读提示，不得创建该 run。

#### Scenario: 重名被拒绝

- **WHEN** 用户以一个已存在 run 同名的名称发起评测
- **THEN** 系统返回 409 并提示名称已存在，不创建新 run

#### Scenario: 唯一名称正常创建

- **WHEN** 用户以未被占用的名称发起评测
- **THEN** 系统正常创建 run 并开始执行

### Requirement: 删除评测 run

系统 SHALL 提供 `DELETE /api/runs/{run_id}`，删除指定 run 及其级联用例结果，并清理其
产物目录；运行中或等待中的 run MUST NOT 被删除（返回 400）。删除不存在的 run 返回 404。

#### Scenario: 删除已完成的 run

- **WHEN** 用户删除一个已完成（成功/失败）的 run
- **THEN** 系统删除该 run 与其用例结果，返回 204，后续查询该 run 返回 404

#### Scenario: 运行中不可删除

- **WHEN** 用户删除一个状态为 running 或 pending 的 run
- **THEN** 系统返回 400 并提示运行中不可删除

#### Scenario: 删除不存在的 run

- **WHEN** 用户删除一个不存在的 run id
- **THEN** 系统返回 404

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

### Requirement: 重判可带配置覆盖

`POST /api/runs/{run_id}/rejudge` SHALL 接收可选 body，允许对本次重判临时覆盖判分相关配置，
而 MUST NOT 修改服务器 `config.yaml`：

- `judge`：合并进 `config.judges.llm/scoring_point`（provider/model/base_url/api_key），
  重判用新判分模型重跑 LLM judge；`api_key` MUST NOT 入库；
- `cases_benchmark_id`：用该 benchmark 的用例判据按 `sample_id` 替换源 run 的冻结用例，
  trace 仍冻结，重跑判分。

覆盖仅作用于本次重判产出的新 run；bot 会话留痕始终冻结。无 body 时行为与既有重判一致。
`cases_benchmark_id` 指向不存在的 benchmark MUST 返回 400。系统 MUST NOT 提供对四模块满分权重
/ 阈值（`scoring`）的重判覆盖（权重为 profile 自适应，顶层覆盖语义割裂，故不暴露）。

#### Scenario: 换 judge 模型重判

- **WHEN** 用户对某 run 重判并传入 `judge` 覆盖（如新的 model）
- **THEN** 新 run 用该 judge 模型重跑判分，且服务器 `config.yaml` MUST 保持不变

#### Scenario: 用改后判据重判

- **WHEN** 用户重判并传入 `cases_benchmark_id` 指向一个改了判据的 benchmark
- **THEN** 系统按 `sample_id` 用该 benchmark 的用例判据替换冻结用例后重跑判分，bot 回答不变

### Requirement: 改 case 判据派生新 benchmark

系统 SHALL 提供两种派生方式，均**复制源 benchmark 全部用例、按 `sample_id` 只覆盖判据字段**
（`expected_behavior` / `hard_gates` / `rubric` / `scoring_points`，其余字段如 `turns` 不动），
逐条经 `TestCase` schema 校验（非法 MUST 拒绝并返回错误），通过后**另存为一个新的 uploaded
benchmark**，并 MUST 记录 `created_by` 为当前登录用户。该操作 MUST NOT 修改源 benchmark（含内置集）。

- 结构化：`POST /api/benchmarks/{benchmark_id}/derive`（`case_overrides` 列表）；
- YAML：`POST /api/benchmarks/{benchmark_id}/derive-yaml`（`yaml_text` 整段用例 YAML）。

派生时若覆盖项的 `sample_id` 在源 benchmark 中**不存在 MUST 跳过丢弃**（不新增、不报错）；
若**没有任何 `sample_id` 命中** MUST 拒绝并返回可读错误。该派生本身 MUST NOT 触发重判。

#### Scenario: 派生不影响源 benchmark

- **WHEN** 用户基于某 benchmark 改若干用例判据并派生
- **THEN** 系统创建一个含改后判据的新 benchmark，源 benchmark 的用例 MUST 保持原样

#### Scenario: 未匹配 sample_id 丢弃、零匹配报错

- **WHEN** 提交的 YAML 含源集中不存在的 `sample_id`
- **THEN** 这些条目 MUST 被丢弃；若一条都没匹配上，系统 MUST 拒绝派生并返回可读错误

#### Scenario: 仅判据字段生效

- **WHEN** 用户在 YAML 里同时改了某用例的 `turns` 与 `hard_gates`
- **THEN** 新 benchmark MUST 只采用改后的 `hard_gates`，`turns` 保持源用例原样

#### Scenario: 非法判据被拒绝

- **WHEN** 派生请求中某条用例覆盖不符合 `TestCase` schema
- **THEN** 系统 MUST 拒绝派生并返回可读的校验错误

### Requirement: benchmark 记录并展示上传人

系统 SHALL 在上传或派生 benchmark 时把当前登录用户写入 `Benchmark.created_by`，并通过
`BenchmarkOut` 透出该字段；未登录（dev 放行）时 created_by 可为空。

#### Scenario: 上传人随 benchmark 落库并返回

- **WHEN** 已登录用户上传或派生一个 benchmark
- **THEN** 该 benchmark 的 `created_by` 记录其身份，列表/详情 API MUST 返回该字段

### Requirement: 导出过滤用例的完整 YAML 供在线编辑

系统 SHALL 提供 `GET /api/runs/{run_id}/cases-yaml`，接收与 `GET /api/runs/{run_id}/cases`
相同的过滤参数（level / release_passed / stability / scenario / tag），并 SHALL 额外支持可选的
`sample_id` 过滤参数以**只导出单条指定用例**的 YAML（供用例明细页就地编辑）。系统返回该 run 命中用例在其
benchmark 中的**完整用例 YAML 文本**（可被 `load_cases` 解析），供前端预填判据编辑器。run 无关联
benchmark、过滤后无用例、或指定的 `sample_id` 不在命中集时 MUST 返回 400。

#### Scenario: 按过滤导出可解析 YAML

- **WHEN** 用户带过滤参数请求某 run 的 cases-yaml
- **THEN** 返回的 YAML MUST 仅含命中用例的完整定义，且可被 `load_cases` 解析校验

#### Scenario: 按 sample_id 导出单条用例 YAML

- **WHEN** 用户带 `sample_id` 参数请求某 run 的 cases-yaml
- **THEN** 返回的 YAML MUST 仅含该单条用例的完整定义，可被 `load_cases` 解析校验

### Requirement: 登录会话 token 续期失败时优雅降级

系统 MUST 把飞书拒绝 `refresh_token` 的续期失败（如 `code=20064` 失效/吊销）视为会话过期处理，MUST NOT 将底层 OAuth 异常作为未处理错误向上抛出。具体而言：

- "可选登录"依赖（用于读取 `created_by` 等署名信息的接口）在续期失败时 MUST 清理该会话并
  返回未登录（None），使接口仍能完成（署名记为空）；
- 任意使用该可选依赖的接口（如 `POST /api/benchmarks/{id}/derive-yaml`、benchmark 上传/派生）
  MUST NOT 因会话过期而返回 500。

#### Scenario: 会话过期不再 500

- **WHEN** 用户飞书会话已过期（refresh 被拒），调用一个用"可选登录"获取署名的接口
- **THEN** 系统 MUST 清理过期会话、以未登录身份完成请求，MUST NOT 返回 500

### Requirement: 人工审核队列

系统 SHALL 提供按 run 的人工审核队列。某 run 的用例 MUST 入队当且仅当满足任一：
(a) `case_result.needs_human_review = true`；(b) `release_passed = false`（原因记 `release_failed`）；
(c) 红旗题且 `release_passed = false`（额外标注 `red_flag_failed`）；(d) 任一 verdict 的
`score_dispersion` ≥ 0.5（原因记 `high_dispersion`）；(e) 与可比基线 run 对比存在剧烈变化（原因记 `cross_run_diff`）。
`GET /api/runs/{run_id}/review-queue` 行为不变（返回结构含 `reasons`）。

可比基线 run MUST 满足：当前 run 的 `diff_against_run_id` 指向的成功 run，或自动解析的上一成功同 benchmark run；
且双方 `judge_fingerprints` 相等。剧烈变化 MUST 指以下任一：
`release_passed` / `hard_gate_passed` / `gate_passed` 与基线不同；`|composite_score 差| ≥ 0.25`；
任一 `dimension_scores` 键的差 ≥ 0.15。

#### Scenario: 跨版本综合分骤降入队

- **WHEN** 当前 run 与可比基线 run 中同一 `sample_id` 的 `release_passed` 均为 true，但综合分从 0.92 降至 0.65
- **THEN** 该用例 MUST 出现在 review-queue，且 `reasons` MUST 含 `cross_run_diff`

#### Scenario: 判分尺子不可比时跳过

- **WHEN** 基线 run 与当前 run 的 `judge_fingerprints` 不一致
- **THEN** 系统 MUST NOT 因跨版本对比将该用例入队（其它入队规则仍适用）

### Requirement: 人工裁定记录且不回写判分

系统 SHALL 提供 `POST /api/runs/{run_id}/cases/{sample_id}/annotate`，记录一条裁定
（`verdict` ∈ {`agree`,`override`}、可选 `suggestion`/`comment`），`reviewer` 取当前飞书登录用户
显示名（未登录可空）。同一用例 MUST 允许多条裁定。`verdict` 非法 MUST 返回 422，用例不在该 run
MUST 返回 404。裁定 MUST NOT 修改该用例的任何判分字段（`verdict`/`score`/`release_passed`/
`gate_passed`/`hard_gate_passed`）——人审是独立旁路层。`GET /api/runs/{run_id}/review-stats`
SHALL 返回队列总数、已审/待审数、agree/override 数与人审通过率/分歧率。

#### Scenario: 裁定落库不影响判分

- **WHEN** 用户对某用例提交 agree 或 override 裁定
- **THEN** 系统 MUST 记录该裁定（含 reviewer），且该用例的 `release_passed` 与 `composite_score`
  等判分字段 MUST 保持不变

#### Scenario: 统计口径

- **WHEN** 队列中部分用例已被裁定
- **THEN** review-stats MUST 返回正确的已审/待审计数与 agree/override 占比

### Requirement: 平台落库必须包含 token/cost 观测字段

评测结果入库时，run 级记录 MUST 持久化 `RunReport.token_summary`，case 级记录 MUST 持久化该用例的总 token 与（配置单价时的）cost。这些字段 MUST 仅作观测保留，MUST NOT 参与平台侧任何通过/失败判定或排序默认口径。新增数据库列 MUST 对历史库向后兼容（带默认值 / 可空），读取历史无该字段的 run 时 MUST 安全返回空值。

#### Scenario: 入库保留 token_summary

- **WHEN** 一次含 token 数据的评测结果被 ingest
- **THEN** run 行 MUST 含 `token_summary`，对应 case 行 MUST 含总 token（及配置单价时的 cost）

#### Scenario: 历史 run 缺字段安全读取

- **WHEN** 读取一个入库时尚无 token 字段的历史 run
- **THEN** API MUST 返回空的 token 字段，MUST NOT 报错

### Requirement: 数据库附加列幂等迁移由 ORM 元数据驱动

系统 SHALL 在启动建表后，由 ORM 元数据（`Base.metadata`）驱动幂等补齐旧库缺失的列：对每张已存在
的表，凡 ORM 中存在而库中缺失、且「可空或带默认值」的列 MUST 以可空形式 `ALTER TABLE ADD COLUMN`
追加；NOT NULL 且无默认的列 MUST 跳过（留待完整迁移）。新增 ORM 列 MUST NOT 依赖任何手工维护的
列登记表。JSON 列 MUST 以合法空 JSON（对象 `{}`，默认 list 的列用 `[]`）作为追加默认值，且系统
MUST 把非空 JSON 列中存量为 NULL 的值回填为空 JSON，避免响应模型校验失败。
已从 ORM 移除的遗留列（含 `case_result.review_requested`）MUST 由 `_drop_obsolete_columns` 幂等
`DROP COLUMN`，避免 INSERT 时 `NotNullViolation`。

#### Scenario: 旧库缺列自动补齐

- **WHEN** 旧库的某表缺少 ORM 中新增的可空/带默认列
- **THEN** 启动迁移 MUST 自动补齐该列且可重复执行（幂等），后续查询 MUST NOT 因缺列报错

#### Scenario: 非空 JSON 列的 NULL 自愈

- **WHEN** 某非空 JSON 列在旧库中存在为 NULL 的存量行
- **THEN** 迁移 MUST 将其回填为合法空 JSON，使读取该行的响应 MUST NOT 因 JSON 为空而 500

#### Scenario: 遗留 review_requested 列被清理

- **WHEN** 旧库 `case_result` 仍含 `review_requested NOT NULL` 列且 ORM 已无该字段
- **THEN** `init_db` MUST DROP 该列，新评测落库不得因该列失败

### Requirement: 平台后端分层

Run 重判 / 试判的 HTTP 校验与派生 run 编排 MUST 位于 `server/services/rejudge_launch.py`（或等价
service）；`routers/runs/rejudge.py` MUST 仅负责 HTTP 绑定与异常映射。

#### Scenario: 重判端点行为不变

- **WHEN** 客户端 `POST /api/runs/{id}/rejudge` 携带合法 payload
- **THEN** HTTP 状态码、响应 JSON 与下沉前一致

### Requirement: 失败标签中文标签元数据接口

系统 SHALL 提供 `GET /api/config/failure-tags`，返回 `FailureTag` 受控词表的 `{枚举值: 中文短标签}`
映射（取自 `FailureTag.label_zh`，单一信任源）。该接口 MUST NOT 重复定义标签文案，前端遇未知值
MUST 回退展示原始枚举值。

#### Scenario: 返回中文标签映射

- **WHEN** 前端请求 failure-tags 元数据
- **THEN** 响应 MUST 为非空映射，且 `missed_red_flag` MUST 映射为其 `label_zh`（如「漏报红旗」）

### Requirement: 用例列表附带人审摘要

`GET /api/runs/{run_id}/cases` 返回的每条用例 SHALL 附带 `review` 字段：若该用例存在人工裁定，则返回摘要；否则为 `null`。列表查询 MUST 使用列投影排除 `CaseResultRow.detail_json` 大字段；依赖 `detail_json` 的派生展示字段（`n_turns`、`langfuse_trace_url`、`guideline_matched`/`guideline_total`）在列表路径 MAY 为占位或 `null`，完整值 MUST 在用例明细或需按 `turns` 过滤时加载 `detail_json` 后计算。

#### Scenario: 列表不加载 detail_json

- **WHEN** 用户请求某 run 的用例列表且未带 `turns` 过滤
- **THEN** 响应 MUST NOT 依赖读取 `detail_json` 全量，`langfuse_trace_url` 与指南命中计数 MAY 为 `null`

#### Scenario: turns 过滤加载明细

- **WHEN** 用户带 `turns=single|multi` 请求用例列表
- **THEN** 系统 MUST 加载 `detail_json` 以正确过滤并返回准确的 `n_turns`

### Requirement: 启动回收孤儿评测任务

评测任务由进程内调度执行，状态仅存于内存。系统启动时 SHALL 回收"孤儿任务"：凡 `eval_run.status`
为 `running` 或 `pending` 的记录 MUST 被标记为 `failed`，并写入可读的 `error_msg` 说明因服务重启
中断，且补齐 `finished_at`。回收 MUST 仅影响 running/pending 记录，对 `success`/`failed` 记录无副作用，
且重复执行幂等。回收后的记录因不再处于 running/pending，MUST 可被删除。

#### Scenario: 重启后回收卡住的任务

- **WHEN** 进程重启时 DB 中存在 status 为 running 或 pending 的 run
- **THEN** 启动回收 MUST 将其置为 failed 并写入中断说明，使其可被删除；success 记录 MUST 保持不变

### Requirement: 修改 benchmark 名称与描述

系统 SHALL 提供 `PATCH /api/benchmarks/{benchmark_id}`，允许修改 benchmark 的 `name` 与
`description`（二者均可选，仅更新提供的字段）。内置（builtin）benchmark MUST NOT 可改，
返回 400。名称若提供则 MUST 非空（去除首尾空白后），空名 MUST 返回 422。benchmark 不存在
MUST 返回 404。此操作 MUST 只改名称/描述，不触碰用例内容与判据。

#### Scenario: 改名与描述

- **WHEN** 用户对一个上传 benchmark 提交新的名称与描述
- **THEN** 系统 MUST 持久化新值并在后续列表/详情返回

#### Scenario: 内置不可改

- **WHEN** 用户尝试 PATCH 内置 benchmark
- **THEN** 系统 MUST 返回 400 且不修改任何字段

### Requirement: 单用例 ephemeral 试判预览

系统 SHALL 提供 `POST /api/runs/{run_id}/cases/{sample_id}/preview-rejudge`：接收针对该 `sample_id`
的判据覆盖（结构化 `CaseLogicOverride`，或等价的单条用例 `yaml_text`，服务端按 sample_id 抽取
`expected_behavior` / `hard_gates` / `rubric` / `scoring_points` 四块），用该 run 中该用例的**冻结
会话留痕**与套用覆盖后的判据，仅重跑判分并重算评分，返回新 verdict 列表、四维分、综合分、上线判定，
以及与该用例当前已存结果的 diff。`yaml_text` 中找不到该 `sample_id` 时 MUST 返回 400。

该端点 MUST 为只读旁路：MUST NOT 写任何库、MUST NOT 新建 run 或产物目录、MUST NOT 复制留痕、
MUST NOT 修改当前 run 的判分、MUST NOT 写入 `case_annotation`。判据合并 MUST 复用与 benchmark 派生
一致的 `sample_id` 覆盖语义；判分 MUST 经与正式重判同一路径（`judge_traces` + 评分），且 MUST NOT
调用被测 bot。

该用例无冻结留痕可用（如 `n_runs>1` 且留痕已被存储治理清理而无法重建代表 trace）时，系统 MUST 返回
400 及可读原因；run 或 `sample_id` 不存在 MUST 返回 404。

#### Scenario: 试判返回新判定且零落库

- **WHEN** 用户对某 run 某用例带编辑后的判据请求 preview-rejudge
- **THEN** 系统 MUST 仅以该用例冻结留痕重跑判分、返回新 verdict / 四维分 / 上线判定及与当前值的 diff，
  且 MUST NOT 写库、MUST NOT 新建 run、MUST NOT 调用被测 bot、MUST NOT 改动当前 run 的判分

#### Scenario: 留痕缺失无法试判

- **WHEN** 目标用例的冻结留痕已被清理且无法重建代表 trace
- **THEN** 系统 MUST 返回 400 并提示无可用留痕、无法试判

#### Scenario: 用例不存在

- **WHEN** 请求的 `sample_id` 不在该 run 的结果中
- **THEN** 系统 MUST 返回 404

### Requirement: Pairwise 对比发起 API

平台 SHALL 提供 `POST /api/compare/pairwise`，入参两个 run id（A 基线 / B 本次）与裁判
模型（取自判分模型库）。校验通过后 MUST 异步发起逐题 PK，立即返回一个
`PairwiseComparison` 记录（`status=running`）。后台任务 MUST 对两 run 共有的
`sample_id` 逐题调用 `PairwiseComparator` 并落库，收尾计算汇总并置 `status=done`；
执行异常 MUST 置 `status=failed` 且不影响既有评测数据。

#### Scenario: 合法发起返回 running 记录
- **WHEN** 用户对同 benchmark、判分尺子一致的两个 run 发起 pairwise
- **THEN** 返回 `status=running` 的比较记录 id，后台开始逐题判定

#### Scenario: 启动回收孤儿比较任务
- **WHEN** 服务重启后存在 `status=running` 且超时的比较记录
- **THEN** 平台启动时 MUST 将其回收为 `failed`

### Requirement: Pairwise 可比性校验

平台 SHALL 在发起前做可比性校验，**只卡判分尺子、放开被测 bot**。两个 run MUST 满足：
①`benchmark_id` 相同；②`sample_id` 集合完全一致；③判分尺子一致（`judge_fingerprints`
相等且 `config_snapshot.scoring` 相等）；④双方均已落 trace（`has_traces`）。任一不满足
MUST 拒绝（HTTP 422）并返回中文原因。被测参数（system_prompt / 被测 model）的差异
MUST NOT 拦截，而是计算为 `subject_diff` 随结果返回。

#### Scenario: 判分尺子不一致被拒
- **WHEN** 两个 run 的 `judge_fingerprints` 不同
- **THEN** 平台 MUST 返回 422 并提示「判分尺子不同，结果不可比」

#### Scenario: 被测 prompt 不同允许对比
- **WHEN** 两个 run 仅 `system_prompt` 不同，其余尺子一致
- **THEN** 平台 MUST 允许发起，并在结果中以 `subject_diff` 标明该差异

#### Scenario: 缺 trace 被拒
- **WHEN** 任一 run 未落 trace
- **THEN** 平台 MUST 拒绝并提示缺少留痕无法对比

### Requirement: Pairwise 结果查询 API

平台 SHALL 提供 `GET /api/compare/pairwise/{id}`，返回整体总结（胜/平/负计数、低置信
计数、按安全/功能/体验维度的胜率、回退用例清单、`subject_diff`）与逐用例列表（每条含
`sample_id`、`winner`、`confidence`、`dimension_winners`、`reason`）。结果 MUST 自落库
读取，不重新调用裁判。

#### Scenario: 返回总结与逐用例
- **WHEN** 比较 `status=done` 后查询结果
- **THEN** 返回整体胜率与维度胜率，以及可逐题查看的对比列表

### Requirement: Pairwise 数据建模与迁移

平台 SHALL 新增 `PairwiseComparison`（run_a_id/run_b_id/judge_model/judge_fingerprint/
status/total_cases/done_cases/汇总 JSON/`note`/created_by/created_at）与 `PairwiseCaseVerdict`
（comparison_id/sample_id/winner/confidence/dimension_winners/reason/swap_consistent/
`scenario`/`sub_scenario`/两次 pass 留痕 `order_runs`/人工校准字段 `human_calibrated`、
`human_winner`、`human_dimension_winners`、`human_reason`、`human_calibrated_by`、
`human_calibrated_at`）两表，并以轻量幂等迁移（启动建表 + ORM 驱动的附加列 `ALTER TABLE ADD
COLUMN` 自动补齐）落库，MUST NOT 破坏既有数据。后续新增的可空/带默认列（如 `order_runs`、
`human_*`、`note`、判分模型的 `pairwise_concurrency`）MUST 由该附加列迁移自动补齐、无需手工迁移脚本。

#### Scenario: 启动幂等建表
- **WHEN** 服务启动且新表不存在
- **THEN** 平台 MUST 自动创建两张新表，已存在时跳过且不报错

### Requirement: Pairwise 对比的备注与删除

每次 Pairwise 对比 MUST 可携带一段自由文本备注 `note`（对比目的），默认空串。发起接口
`POST /api/compare/pairwise` MUST 接受可选 `note` 并持久化；读取/列表接口 MUST 回显 `note`。
系统 MUST 提供 `PATCH /api/compare/pairwise/{id}` 二次编辑 `note`（对不存在的 id 返回 404），
且该接口 MUST NOT 改动除 `note` 外的任何字段（不影响判分、汇总、可比性）。

系统 MUST 提供 `DELETE /api/compare/pairwise/{id}` 物理删除一次对比记录，并 MUST 级联删除其
全部逐用例结论（`PairwiseCaseVerdict`）。删除成功 MUST 返回 204；对不存在的 id MUST 返回 404。

#### Scenario: 发起时写入备注并回显

- **WHEN** 以 `note="验证 v6 prompt 收紧后安全是否退化"` 发起对比
- **THEN** 该对比记录 MUST 持久化该 `note`，列表与详情接口 MUST 回显相同 `note`

#### Scenario: 二次编辑备注

- **WHEN** 对已存在的对比 `PATCH` 一个新的 `note`
- **THEN** 该对比的 `note` MUST 被更新为新值，其余字段 MUST 保持不变

#### Scenario: 删除连带清空 verdict

- **WHEN** 删除一个已有逐用例结论的对比
- **THEN** 该对比记录与其全部 `PairwiseCaseVerdict` MUST 被一并删除，后续查询 MUST 返回 404

### Requirement: Pairwise 逐用例人工校准

系统 MUST 允许对已完成的 Pairwise 对比逐用例进行人工校准，覆写有效结论、三维度归属与理由；
校准后 `confidence_kind` MUST 为 `human`。机器原判字段 MUST 保留且 MUST NOT 被校准覆盖。
`DELETE` 同用例校准 MUST 恢复为机器有效值并重算汇总。

校准或恢复后，`PairwiseComparison.summary` MUST 按全部用例的**有效值**立即重算（胜/平/负、
低置信细分、维度胜率、overall_winner、回退/改善清单），列表与详情 MUST 回显重算结果。

#### Scenario: 人工改结论后汇总联动

- **WHEN** 某用例机器判 `tie` 被人工校准为 `winner=B`
- **THEN** 该对比的 `summary.b_wins` MUST 递增、`summary.ties` MUST 递减，且 `overall_winner`
  等统计 MUST 与有效值一致

#### Scenario: 恢复机器判定

- **WHEN** 对已校准用例执行恢复
- **THEN** 有效值 MUST 回到机器原判，summary MUST 按机器口径重算

### Requirement: 产物路径边界安全

系统 SHALL 保证所有由 `run_name`/slug/benchmark 标识拼接出的文件系统路径都限制在受控根目录（`outputs/`、`uploads/`）之内。`run_slug` 生成 MUST 对名称做字符白名单消毒，去除路径分隔符与 `..` 等穿越片段；任何读/写/删除产物前 MUST 经统一 `safe_join` 校验目标路径 `is_relative_to` 受控根，越界 MUST 拒绝（HTTP 400）。本需求 MUST NOT 改变既有合法 slug 的产出结果。

#### Scenario: 含穿越片段的 run 名称被消毒

- **WHEN** 以包含 `../` 或路径分隔符的 `run_name` 发起评测或解析其产物目录
- **THEN** 系统 MUST 生成限制在 `outputs/` 内的安全 slug，且对应产物路径 MUST 落在 `outputs/` 根之内

#### Scenario: 越界产物路径被拒绝

- **WHEN** 任意端点尝试访问解析后落在受控根之外的产物路径
- **THEN** 系统 MUST 拒绝该操作并返回错误，而非读写根目录之外的文件

### Requirement: benchmark 上传大小上限

系统上传 benchmark YAML 的端点 SHALL 限制请求体大小，超过上限 MUST 拒绝并返回可读错误（HTTP 413/400），以避免超大上传导致内存耗尽。上限 MUST 可经配置调整。

#### Scenario: 超限上传被拒绝

- **WHEN** 用户上传超过配置上限的文件
- **THEN** 系统 MUST 拒绝保存并返回大小超限的错误信息，不读入全部内容

### Requirement: 生产环境会话密钥强校验

当运行于生产环境时，系统 SHALL 拒绝使用默认/不安全的 `SESSION_SECRET` 启动：若检测到生产环境且密钥仍为内置默认值，启动 MUST 失败并给出明确错误。HTTPS 部署下会话 cookie SHALL 标记 `Secure`。开发/测试环境 MUST 保持现有默认值可直接启动。

#### Scenario: 生产使用默认密钥启动失败

- **WHEN** 在生产环境标识下以默认 `SESSION_SECRET` 启动服务
- **THEN** 启动 MUST 失败并提示需配置安全密钥

#### Scenario: 开发环境默认密钥可用

- **WHEN** 在开发/测试环境以默认配置启动
- **THEN** 服务 MUST 正常启动，行为与现状一致

### Requirement: 运行列表分页

`GET /api/runs` SHALL 支持分页参数 `limit`（默认 50，最大 100）与 `offset`。`GET /api/benchmarks`、`GET /api/judge-models`、`GET /api/compare/pairwise` 与 `GET /api/runs/{run_id}/cases` SHALL 采用相同默认与上限。未显式传 `limit` 时 MUST 应用默认 50。

#### Scenario: 默认请求受默认上限约束

- **WHEN** 不带 `limit` 请求运行列表且库内记录超过 50 条
- **THEN** 系统 MUST 最多返回 50 条

#### Scenario: 带分页参数请求

- **WHEN** 带 `limit`/`offset` 请求运行列表
- **THEN** 系统返回对应分页切片，且 `limit` 超过 100 MUST 被拒绝

### Requirement: 全局异常处理与优雅关闭

系统 SHALL 注册全局异常处理器，将未捕获异常与请求校验错误统一为结构化错误响应（生产环境 MUST NOT 泄漏堆栈细节）。应用 `lifespan` SHALL 在关闭阶段优雅收尾后台任务（评测/对比任务），避免进程退出时丢失或半写状态。

#### Scenario: 未捕获异常返回统一错误体

- **WHEN** 某请求处理过程中抛出未预期异常
- **THEN** 系统 MUST 返回统一格式错误响应，生产环境不暴露内部堆栈

#### Scenario: 关闭时收尾后台任务

- **WHEN** 服务收到关闭信号且存在进行中的后台任务
- **THEN** `lifespan` shutdown MUST 尝试取消/等待这些任务收尾

### Requirement: Container deployment

The platform MUST support deployment via Docker: a multi-stage image that builds the frontend and runs the FastAPI application with static asset hosting on port 8000.

The repository MUST provide `docker-compose.yml` orchestrating the application service with PostgreSQL, persistent volumes for `outputs/` and `uploads/`, and a health check against `GET /api/health`.

Production container runs MUST set `MEDEVAL_ENV=production` and MUST NOT use the default `SESSION_SECRET`; secrets and `config.yaml` SHALL be supplied via environment variables or mounted files, not baked into the image.

#### Scenario: Compose startup with health check

- **WHEN** an operator runs `docker compose up --build` with a valid `.env` and `SESSION_SECRET`
- **THEN** the `app` service SHALL start uvicorn on port 8000, serve the built frontend, and respond `{"status":"ok"}` from `GET /api/health`
- **AND** `outputs/` and `uploads/` data SHALL persist across container restarts via mounted volumes

### Requirement: Production static hosting MUST fallback SPA routes to index.html

When `frontend/dist` exists, the platform MUST serve built static files and MUST return `index.html` with HTTP 200 for client-side routes (e.g. `/runs`, `/runs/1`) that do not map to a physical file under `dist/`. Requests under `/api/` MUST continue to be handled by API routers and MUST NOT be overridden by the SPA fallback.

#### Scenario: Direct navigation to /runs

- **WHEN** a GET request is made to `/runs` and `frontend/dist/index.html` exists
- **THEN** the response MUST be HTTP 200 with the `index.html` body

#### Scenario: Static asset still served

- **WHEN** a GET request is made to `/assets/main.js` and the file exists under `frontend/dist/assets/`
- **THEN** the response MUST be HTTP 200 with the file contents

### Requirement: Platform MUST expose judge verdict Chinese labels via config API

The eval platform service MUST expose `GET /api/config/judge-verdict-labels` returning a JSON object mapping judge verdict names (e.g. `hard_gate.red_flag`, `llm.empathy`) to Chinese display labels. Labels MUST be sourced from `medeval.judge_labels` as the single trust source. Existing REST paths and response schemas for other endpoints MUST NOT change.

#### Scenario: Fetch judge verdict labels

- **WHEN** a client requests `GET /api/config/judge-verdict-labels`
- **THEN** the response MUST be HTTP 200 with a JSON object containing at least `hard_gate.red_flag` and `llm.empathy` keys

### Requirement: Token cost computation MUST use a single shared implementation

Per-case token and cost computation for DB ingest MUST call the shared function in `medeval.reporter.token_cost`. Run-level token aggregation in the reporter MUST use the same cost formula helper. Numeric outputs for identical inputs MUST remain unchanged from pre-refactor behavior.

#### Scenario: Ingest token cost unchanged

- **WHEN** `build_case_row` processes a `CaseResult` with known token usage and pricing
- **THEN** `total_tokens` and `cost` columns MUST match pre-refactor characterization fixtures

### Requirement: Run helper logic MUST reside in server services layer

Run-related query and case-row enrichment logic that was in `server/routers/runs/_helpers.py` MUST be implemented in `server/services/runs.py` and `server/services/case_query.py`. HTTP handlers MUST import from these service modules only. REST paths, status codes, and response JSON MUST remain unchanged.

#### Scenario: Review queue API unchanged

- **WHEN** a client requests `GET /api/runs/{id}/review-queue` after P0
- **THEN** the response MUST match pre-refactor filtering and `reasons` semantics for the same run data

### Requirement: Platform domain routers MUST delegate to service layer

HTTP handlers for judge models, dashboard trends, config release thresholds, HITL review, and pairwise comparison MUST delegate business logic to `server/services/*` modules. Routers MUST NOT execute SQLAlchemy queries directly after P1. REST paths and response JSON MUST remain unchanged.

#### Scenario: Judge model CRUD unchanged

- **WHEN** a client performs create/list/update/delete on `/api/judge-models` after P1
- **THEN** HTTP status codes and response bodies MUST match pre-refactor behavior

### Requirement: Benchmark and run catalog routers MUST delegate to service layer

After P2, `routers/benchmarks.py`, `routers/runs/crud.py`, and `routers/runs/cases.py` MUST NOT contain SQLAlchemy queries or multi-step business orchestration; they MUST call `server/services/benchmark_catalog.py`, `server/services/runs.py`, and `server/services/case_export.py` respectively. REST behavior MUST remain unchanged.

#### Scenario: Create run API unchanged

- **WHEN** `POST /api/runs` is called with a valid payload after P2
- **THEN** the response MUST match pre-refactor status code and `RunSummaryOut` fields

### Requirement: Run 人审校准一致性 API

系统 MUST 提供 `POST /api/runs/{run_id}/calibration`，接受上传的人审打分表（YAML/JSON），
与指定 run 的 `report.json` 对齐计算人机一致率（如 Cohen's kappa、逐维 Pearson 等），
MUST NOT 回写任何判分字段。

#### Scenario:校准成功返回度量

- **WHEN** 客户端上传合法人审表且 run 目录存在 `report.json`
- **THEN** 响应 MUST 含 `sample_count` 与一致性度量字段，HTTP 200

#### Scenario:无 report 返回 404

- **WHEN** run 存在但无 `report.json`
- **THEN** MUST 返回 HTTP 404

