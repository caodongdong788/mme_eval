## Context

`medeval` 当前是 CLI-first 框架，核心编排函数 `medeval.service.evaluate(config, cases, adapter, judges, adjudicator)` 已是**纯异步、无副作用**（除 adapter 网络调用），返回 `RunReport`；配套 `build_adapter / build_judges / build_adjudicator / load_cases / load_config` 都是现成构造器。进度通过 `ProgressObserver` 协议上报。结果仅以文件形式存在 `outputs/<slug>/report.json`，无 DB、无 API、无前端。

本次在其之上叠加平台层。约束：

- 不修改判分核心（`judges/**`、`models.py`、HardGate 治理、scoring profile）。
- Python 3.12（项目 `.venv`），pydantic v2。
- 现阶段单人本地使用，但架构须为未来服务器多人并发预留。

## Goals / Non-Goals

**Goals:**

- 网页发起评测 → 后端复用 `evaluate()` 执行 → 结果落库 → 看板与明细呈现。
- benchmark 库：上传/校验/命名/版本/复用，内置现有乳腺癌套件。
- 发起评测时可配置评测打分模型（judge 的 provider/model/base_url/api_key）。
- 数据库与任务执行可平滑扩展到 Postgres 与外部队列。

**Non-Goals:**

- 不做登录鉴权 / 多租户 / 角色权限（仅预留字段与架构）。
- 不修改 `medeval` 判分与报告核心逻辑。
- 不引入 Celery/Redis 等外部 broker（MVP 用进程内任务）。
- 不做人工标注界面、IAA 等 P3 能力。

## Decisions

- **后端框架 FastAPI**：异步原生，契合 `evaluate()` 的 async 编排，可直接 `await`；相比 Flask 更省去线程包装。
- **复用 service 层而非重写**：发起评测时把网页传入的 judge 模型参数合并进 `config.judges.llm` / `config.judges.scoring_point`，再调 `build_judges` + `evaluate`，判分逻辑零改动。被测 bot 沿用 `config.yaml` adapter（可选覆盖）。
- **持久化 SQLAlchemy ORM + SQLite 起步**：`DATABASE_URL` 配置化，一行切 Postgres。表设计「标量列 + JSON 列」混合：看板聚合走标量列（`level/release_passed/composite_score/stability/...`），明细页读 `case_result.detail_json`（完整 `CaseResult` 的 `model_dump`）。替代方案「整份 report.json 塞一个 JSON blob」被否决：无法做跨 run/跨 case 聚合查询。
- **评测任务用 `JobRunner` 抽象 + 进程内 asyncio 实现**：发起评测立即建 `eval_run(status=pending)` 并返回 id，后台 asyncio task 执行，状态机 `pending→running→success/failed`，并发用 `Semaphore` 限流；进度通过实现 `ProgressObserver` 写入内存/DB 供前端轮询。未来替换为外部队列时只换 `JobRunner` 实现。
- **benchmark 存储**：上传 YAML 落 `uploads/benchmarks/<id>/`，用现有 `load_cases` 校验后写 `benchmark` 元数据行；内置 `cases/breast_cancer` 作为 `source=builtin` 行（指向仓库路径）。发起评测时按 benchmark 解析出用例路径喂 `load_cases`。
- **前端 React + TS + Ant Design + 图表库（Recharts）**：AntD 表格/表单/布局开箱即用，适合后台看板；Vite 开发，构建产物由 FastAPI 静态托管，一条命令拉起。
- **双写兼容**：落库的同时调用现有 `write_core_artifacts` 写 `outputs/`，保持与 CLI 一致与可回溯。

## Risks / Trade-offs

- SQLite 并发写较弱 → 现阶段单人无碍；上服务器多人前切换 `DATABASE_URL` 到 Postgres（ORM 已抽象，迁移成本低）。
- 进程内任务随进程重启丢失运行中任务 → MVP 可接受；重启后将 `running` 视为中断态，未来队列化解决。
- `case_result.detail_json` 体积较大（含完整对话/verdict）→ 列表查询只取标量列，明细页才读 JSON，避免列表慢查询。
- judge 模型 api_key 经网页传入 → 仅本地使用、不入库明文（`judge_overrides` 存非密参数；api_key 走环境变量或运行期内存，不持久化）。

## Migration Plan

- 纯新增，无数据迁移。首次启动自动建表（`create_all`）。
- 历史 `outputs/*/report.json` 通过一次性导入工具落库（可选）。
- 回滚：删除 `server/`、`frontend/` 与 DB 文件即可，`medeval` CLI 不受影响。

## Open Questions

- 进度上报粒度（按 case 还是按 phase）——初版按 phase + 已完成 case 数，足够前端进度条。
- 趋势看板的「同一基线」如何界定（按 benchmark + adapter 维度分组）——初版按 benchmark 分组展示时间序列。
