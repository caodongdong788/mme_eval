# MME · Agent 评测平台（后端 + 前端）

在 `medeval` CLI 框架之上叠加的本地评测平台：网页发起评测 → 后端复用 `medeval.service.evaluate()` 执行 → 结果落库 → 看板与用例明细呈现。判分核心（`medeval/judges`、`models.py`、`reporter`）零改动。

参见 OpenSpec change `add-eval-platform`。

## 架构

- 后端 `server/`（FastAPI + 同步 SQLAlchemy）
  - `app.py` 应用入口（lifespan 建表 + 生产安全校验 + 回收孤儿任务，含回收孤儿 pairwise；shutdown 优雅取消在跑评测）；`settings.py` 环境变量；`deps.py` 公共依赖（`creator_name` 等）；`paths.py` 产物路径 `safe_join` 边界校验；`db.py` 引擎/会话/建表（ORM 驱动附加列 + 幂等补索引）；`models_db.py` ORM 表（`benchmark` / `eval_run` / `case_result` / `case_annotation` / `pairwise_comparison` / `pairwise_case_verdict` / `judge_model_config`）
  - `ingest.py` `RunReport`→DB 落库；`jobs.py` `JobRunner`（进程内 asyncio，并发上限 + 状态机）+ `reconcile_orphaned_runs()`；`progress.py` 进度
  - `benchmarks.py` benchmark 库（上传/校验/内置注册；改判据派生新集 `derive_benchmark_with_overrides` / `derive_benchmark_from_yaml`，就地覆盖原集 `overwrite_benchmark_from_yaml`）；`eval_job.py` 评测任务（合并打分模型覆盖 + 落会话留痕 + 双写 outputs + 收尾存储治理；含离线重判 / 断点续跑两个 job）
  - `routers/` REST API：`benchmarks`（含 `derive` / `derive-yaml` / `PATCH` 改名）/ `runs`（含 `rejudge` / `resume` / `pin` / `cases-yaml` / `review-queue` / `annotate` / `review-stats`）/ `dashboard` / `cases` / `compare`（Pairwise：发起 / 查询 / `PATCH` 备注 / `DELETE` 删除 / 逐用例 `PATCH` 校准 + `DELETE` 恢复）/ `config`（含 `failure-tags`）/ `auth`；`pairwise_job.py` 异步逐题 PK（并发 + 汇总重算）
  - `import_history.py` 历史 `outputs/*/report.json` 导入
- 前端 `frontend/`（Vite + React + TS + Ant Design + Recharts）
  - Benchmark 库、发起评测、评测列表（实时进度）、单次看板、用例明细、跨 run 趋势

## 安装

```bash
pip install -e ".[server]"      # 后端依赖（已含于 .venv）
cd frontend && npm install      # 前端依赖
```

## 启动

开发模式（后端 reload + 前端 dev server，`/api` 自动代理）：

```bash
scripts/dev_platform.sh         # 后端 :8000 + 前端 :5173
```

生产模式（构建前端 → 由 FastAPI 静态托管）：

```bash
scripts/serve_platform.sh --port 8000     # 访问 http://localhost:8000
```

### Docker Compose（推荐上云）

多阶段镜像 + Postgres + 持久化 volume，一次构建可复现部署：

```bash
cp .env.docker.example .env    # 必改 SESSION_SECRET；公网再改 FRONTEND_URL / 飞书回调
docker compose up -d --build   # http://localhost:8000
docker compose logs -f app
docker compose down            # 数据在 volume pgdata / mme-data 中保留
```

要点：

- **单实例**：`JobRunner` 进程内调度，Compose 请只跑一个 `app` 副本。
- **持久化**：评测产物 `outputs/`、上传 benchmark `uploads/` 挂载在 volume `mme-data`；数据库在 `pgdata`。
- **配置**：默认挂载宿主机 `./config.yaml` 到容器（可设 `MEDEVAL_CONFIG_HOST_PATH`）；生产 adapter / judge 在此文件或判分模型库配置。
- **HTTPS**：公网请在前面加 Nginx/Caddy 反代并配证书；`MEDEVAL_ENV=production` 时会话 cookie 需 `Secure`。
- **内网免登录**：`.env` 中不填 `FEISHU_APP_ID` 即 dev 兜底放行（仅可信内网）。

详见仓库根目录 `Dockerfile`、`docker-compose.yml`、`.env.docker.example`。

## 配置（环境变量）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MEDEVAL_DATABASE_URL` | `sqlite:///medeval_platform.db` | 数据库连接串，可切 Postgres |
| `MEDEVAL_CONFIG_PATH` | `config.yaml` | 被测 bot 基础配置（adapter/judges/scoring 口径来源） |
| `MEDEVAL_UPLOADS_DIR` | `uploads/benchmarks` | 上传 benchmark 用例存储 |
| `MEDEVAL_OUTPUTS_DIR` | `outputs` | 评测产物目录（与 CLI 双写兼容） |
| `MEDEVAL_MAX_CONCURRENT_JOBS` | `2` | 并发评测任务上限 |
| `MEDEVAL_ENV` | `development` | 运行环境；`production`/`prod` 时强制非默认 `SESSION_SECRET` 且 cookie `Secure` |
| `MEDEVAL_MAX_UPLOAD_BYTES` | `5242880`（5 MiB） | benchmark 单文件上传大小上限，超限 413 |

## 关键说明

- **打分模型可配**：发起评测时可指定 LLM-as-Judge 的 provider/model/base_url/api_key（现为 gpt，可换更强模型），合并进 `config.judges.llm/scoring_point` 后再装配 judge；被测 bot 默认沿用 `config.yaml`，可选覆盖。`api_key` 仅运行期使用，不入库。
- **双写兼容**：评测结果同时落库与写 `outputs/<slug>/report.json`，与 CLI 互不影响。
- **落会话留痕（与 CLI 对齐）**：网页发起的评测同样把会话留痕落 `outputs/<slug>/traces.jsonl.gz`（gzip，按 `config.run.store_raw` 瘦身 raw_responses），落库置 `eval_run.has_traces`。
- **被测 bot 全链路追踪（Langfuse，可选）**：评测复用内核的 Langfuse 追踪——每条用例一条独立 trace、按 `session_id=run_name` 分组；trace 深链随报告进入用例明细，前端「**追踪链路**」入口（`GET /api/runs/{id}/cases` 与用例明细接口暴露 `langfuse_trace_url`）点击在自托管 Langfuse 打开该用例完整流程。默认开启、软依赖 no-op，未配置/未装 SDK/旧 run 时该字段为空、前端入口隐藏（配置见根 `README.md` 与 `.env.example`）。启用要点：SDK 必须装进**实际跑 server 的解释器**（`dev_platform.sh` 默认 `.venv`，即 `.venv/bin/python -m pip install "langfuse>=4,<5"`），`.env` 配好 `LANGFUSE_*` 后**重启后端**才生效，且只有**新评测**会被追踪（旧 run/重判不回填）。
- **离线重判 `POST /api/runs/{id}/rejudge`**：对源 run 的**冻结用例 + 冻结留痕仅重跑判分（零 bot 调用）**，产出一个 `parent_run_id` 指向源 run 的**新 run**，默认与源 run 对比，凸显「判分逻辑变化」单变量。看板右上「重判」按钮触发，弹框可选临时覆盖（仅作用本次重判、不改 `config.yaml`）：
  - `judge_model_id`：从**判分模型库**下拉选一个已保存配置（连接信息 + Key 由服务端注入运行期、`public_dict` 入库剔除明文 key；前端不再手填）；不存在 → 404。（`judge` 手填覆盖字段保留做 API 向后兼容。）
  - `cases_benchmark_id`：用某个 benchmark 的用例判据按 `sample_id` 替换冻结用例后重判（trace 仍冻结）。
  - `only_release_failed`：**只重判上线判定失败（`release_passed=false`）的用例**——只对失败用例重放留痕重判，通过用例沿用源 run 结果，合并后 `build_report` 重算整体分数/通过率/分布（仍产出新 run、源 run 不可变）。源 run 无失败用例 → 400。合并报告的 `judge_fingerprints` 为混合（通过用例沿用源指纹、失败用例用新指纹），属该模式固有语义。
  无 body 时按源 run 原配置重判。400 条件：源 run 非 success / 缺 `report.json`（产物已清理）/ `n_runs>1` 且留痕已被治理清理 / `cases_benchmark_id` 指向不存在的 benchmark / `only_release_failed` 但源无失败用例。
  > 不提供四模块满分权重 / 阈值（`scoring`）的重判覆盖——权重是 profile 自适应的（见根 `README.md`「四模块怎么算」），改顶层只对命中 default 的用例生效、语义割裂，故刻意不暴露。
- **在线改判据 → 另存新 / 覆盖原 benchmark（YAML）**：看板「用例结果」区「编辑判据(YAML)」抽屉，用 `GET /api/runs/{id}/cases-yaml`（同 `/cases` 过滤参数）预填当前过滤命中用例的完整 YAML。保存时**复制源 benchmark 全部用例**、按 `sample_id` **只合并判据字段**（`expected_behavior` / `hard_gates` / `rubric` / `scoring_points`，`turns` 等不动）；YAML 里源集找不到的 `sample_id` 丢弃、源集中未出现的用例保持原样、零匹配报错；逐条过 `TestCase` 校验。两种落点（合并语义完全一致）：
  - **另存新 benchmark** `POST /api/benchmarks/{id}/derive-yaml`：写入一个**新 uploaded benchmark**（含 `created_by`），源集只读不动。
  - **覆盖当前 benchmark** `POST /api/benchmarks/{id}/overwrite-yaml`：把合并结果**就地写回原 benchmark**（复用 `replace_uploaded_benchmark` 落盘/校验）；内置 benchmark 不可覆盖（400）。前端覆盖按钮对内置禁用并二次确认。
  两者均**不触发重判**，也**不影响**任何历史 run 的冻结结果——重判到「重判」弹框选 benchmark 单独发起。
- **上线判定阈值按场景可配 `GET/PUT /api/config/release-thresholds`**：前端「上线判定阈值」页按评分档（profile：default/red_flag/adversarial/knowledge/rehab）设置「综合分上线阈值」——某题综合分达该档阈值即 `release_passed=true`。GET 返回各档 `max_total`（满分上限）/ `default_threshold`（perfect 档=满分、threshold 档=`min_composite`）/ `override` / `effective`；PUT 校验 `0 < x ≤ max_total`、未知 profile 422，值=默认则删除覆盖（恢复默认）。覆盖存 `release_threshold_config` 表，**对之后发起的新评测与重判都生效**（`build_eval_job` / `build_rejudge_job` 均在 load_config 后注入 `config.scoring`、进入 `config_snapshot` 与 `fingerprint`；重判仍冻结 bot 留痕、零 bot 调用，仅判分口径随当前阈值变化，产出新 run）。**只改综合分阈值**，保留该 profile 原有安全/合规 gates 与 HardGate；未配置的 profile 与 `config.yaml` 逐字节一致。⚠️ 红旗/对抗档建议保持满分阈值。配套：用例详情维度分以 `分/满分` 展示（`CaseResult.dimension_max`，取该题 profile `module_max`）。
- **用例详情得分点与指南匹配率**：得分点表区分正分点与惩罚（负分）点——惩罚点未触发显示「未触发·罚则 -N」、已触发显示「已扣 -N」（不再是无意义的 `0/0`），说明带出符号判据；用例详情新增「指南匹配率」`X%（命中/总数）`（按带 guideline 锚点得分点计数，无锚点显示「无指南锚点」）。用例列表「指南匹配率」列同样带命中计数 `X%（命中/总数）`（`CaseRowOut.guideline_matched` / `guideline_total`，服务端从 `detail_json` 派生、零迁移、对历史 run 生效；无锚点显示「无锚点」），并支持过滤（`GET /api/runs/{id}/cases?guideline=full|partial|none`，按 `guideline_match_rate` 过滤；cases-yaml / export 同口径）。
- **断点续跑 `POST /api/runs/{id}/resume`**：复用源 run 成功留痕、仅对失败/缺失用例重调 bot，产出新 run；adapter 指纹不一致由内核续跑逻辑拒绝（不混入不同 bot 的旧留痕）。看板「续跑」按钮触发。可续跑判据为「存在可复用留痕」（`traces.jsonl.gz` 或 `traces.partial.jsonl`），故**被服务重启/崩溃中断、从未写出 `report.json` 的 run 也能续跑**：评测启动即落 `plan.json`（过滤后的实际用例 `sample_ids` + `n_runs`），续跑时无 `report.json` 则从源 run 的 benchmark 按 `plan.json` 重建用例集（缺 plan 回退全量），再以 partial 留痕续跑。二者皆无留痕→400；无 `report.json` 且未关联 benchmark→400。
- **置顶保护 `POST /api/runs/{id}/pin?pinned=`**：切换 `eval_run.pinned` 并在产物目录落/删 `KEEP` 哨兵，使 CLI（`medeval prune`）与平台存储治理共用同一豁免信号。看板「置顶」按钮触发。
- **存储治理收尾**：评测任务完成后按 `config.run.retention`（`keep_last` / `ttl_days` / `keep_tagged`）自动清理历史 run 的胖产物（traces/xlsx），永久保留 `report.json` 与数据库；治理失败不影响评测落库。
- **人工审核队列（HITL）`/api/runs/{id}/review-queue|review-stats`、`/cases/{sid}/annotate|request-review|annotations`**：把"红旗规则失败置 `needs_human_review`"与"上线失败"等线索做成可操作旁路。入队规则 = `needs_human_review` ∪ `release_passed=false`（原因 `release_failed`，红旗失败再叠加 `red_flag_failed`）∪ 手动加入（`case_result.review_requested`）。专家在用例详情页记 `agree`/`override` + 建议/备注（`reviewer` 取飞书登录名），写入 `case_annotation` 表；裁定为**只读旁路、永不回写**任何判分字段（verdict/score/release/gate/hard_gate）。看板「用例结果」加「待审 N」徽标、「仅看待审」（排除已审）、「人审结果」筛选与「人审结果」列（同意/推翻，悬浮看建议备注），并有人审通过率/分歧率统计卡。`/cases` 每行附最新一条裁定摘要 `review`（verdict/reviewer/suggestion/comment/count）。
- **Pairwise 对比 `/api/compare/pairwise`**：LLM Grader 的「相对偏好」分支，对**判分尺子一致**（同 `benchmark_id`、`sample_id` 集合一致、`judge_fingerprints` 与 `config_snapshot.scoring` 相等、双方均 `has_traces`）的两 run（A 基线 / B 本次）逐题 PK；被测参数（system_prompt / model）差异不拦截、以 `subject_diff` 随结果返回，不满足尺子一致则 422。`POST` 校验后异步发起（立即返回 `status=running`，可携 `note`），`pairwise_job.run_pairwise_comparison` 以判分模型的 `pairwise_concurrency`（默认 4，`Semaphore` 题间并发 + `swap_debias` 题内 `gather`，`asyncio.Lock` 护 `done_cases`/落库）逐题调 `PairwiseComparator`，收尾算 `summary` 置 `done`、异常置 `failed`；服务启动回收超时 `running`。`GET /{id}` 自落库读、不重判，返回总结（胜/平/负、低置信细分 `order`/`safety`、维度胜率、`subject_diff`、`overall_winner`）+ 逐用例（`winner`/`confidence_kind`/`dimension_winners`/`reason`/`order_runs`/`scenario`/`sub_scenario`）。`PATCH /{id}` 改 `note`、`DELETE /{id}` 删对比（级联清 `pairwise_case_verdict`）。**逐用例人工校准** `PATCH /{id}/cases/{sid}` 覆写结论/维度/理由（`confidence_kind=human`、保留机器原判于 `auto_*`）、`DELETE` 恢复机器判；校准/恢复后 `recompute_pairwise_summary` 按**有效值**（`verdict_effective_row`：human 优先否则机器）立即重算 `summary`。比较器细节（双盲匿名化消偏 / 医疗保守覆盖 / `fingerprint`）见根 `README.md` 与 `judging-pipeline` spec。
- **启动回收孤儿任务**：评测由进程内 asyncio 调度，状态仅存内存。`init_db` 后 lifespan 调 `jobs.reconcile_orphaned_runs()`，把进程重启/热重载/崩溃残留的 `running`/`pending` run 统一置 `failed`（写中断说明、补 `finished_at`），使其可删、可重新发起（幂等、不动 success/failed）。
- **附加列自动迁移（ORM 驱动）**：`init_db` 建表后由 `Base.metadata` 自动 diff 旧库缺失的「可空/带默认」列并 `ALTER TABLE ADD COLUMN`（含 `has_traces`/`pinned`/`parent_run_id`/`review_requested`/`token_summary`/`cost`/`total_tokens` 等），新增 ORM 列无需手工登记；JSON 列以空 `{}`/`[]` 追加并回填存量 NULL，避免响应模型校验 500。NOT NULL 且无默认的列跳过（留给完整迁移）。
- **生产安全前置校验**：`MEDEVAL_ENV=production` 时，若 `SESSION_SECRET` 仍为内置默认值，lifespan 启动直接失败；生产态会话 cookie 自动 `Secure`（需 HTTPS）。开发/测试默认 `MEDEVAL_ENV=development` 不受影响。
- **产物路径边界校验**：`outputs/`、`uploads/` 下所有路径拼接经 `server/paths.py::safe_join`（`resolve()` + `is_relative_to`），`run_slug` 经 `medeval/run_slug.py` 消毒，防目录穿越。
- **飞书 SSO + 按用户导出**：飞书 OAuth2 登录（会话 cookie + 自动续期），导出对话流水以**当前登录用户**的飞书 token 上传为在线表格；环境变量 `FEISHU_APP_ID/SECRET/REDIRECT_URI/SCOPES`、`SESSION_SECRET`（见 `.env.example`）。配齐密钥才强制登录，否则 dev 放行。
- **会话过期优雅降级**：access_token 临过期会用 refresh_token 自动续期；当飞书拒绝续期（如 `code=20064` 失效/吊销），`ensure_fresh_token` 把它统一转成 `SessionExpired`——"可选登录"接口（如上传/派生 benchmark 取 `created_by`）会清掉过期会话、以未登录身份继续完成（**不再 500**，仅 `created_by` 记为空＝列表显示「未知」，重新登录后恢复署名）；需登录的接口照常回 401。
- **上传人 `created_by`**：上传 / 派生 benchmark 时写入当前登录用户显示名，`BenchmarkOut` 透出，Benchmark 库列表新增「上传人」列（无则「未知」）。未登录（dev 放行）时为空。
- **Benchmark 库：模板入口 + 改名/描述**：列表只展示上传/派生集，内置集从列表抽离、改以页首「用例模板」入口呈现（点击下载内置乳腺癌专科用例 YAML，可改后作为新 benchmark 上传）。`PATCH /api/benchmarks/{id}` 修改名称/描述（内置不可改→400、空名→422），列表每条提供「编辑」弹窗。
- **失败标签中文映射 `GET /api/config/failure-tags`**：返回 `FailureTag` 受控词表的 `{枚举值: label_zh}`（单一信任源），前端看板/详情把失败标签渲染为中文短标签（未知值回退原值）。
- **扩展性**：`MEDEVAL_DATABASE_URL` 一行切 Postgres；`JobRunner` 可换外部队列。

## 历史数据导入

```bash
.venv/bin/python -m server.import_history outputs
```
