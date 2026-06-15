## Why

现有 `medeval` 是纯命令行框架：评测结果只落 `outputs/<slug>/report.json` 文件，没有数据库、没有服务端、没有前端。团队无法在网页上发起评测、对比历史、看聚合看板或下钻单条用例明细。需要在**不改动判分核心**的前提下，叠加一个本地评测平台（后端服务 + 数据库 + 前端看板），并为未来部署到服务器、多人并发预留扩展位。

## What Changes

- 新增 **FastAPI 后端服务**（`server/` 包），直接复用 `medeval.service.evaluate()` 等现成编排函数发起评测，跑完结果落库。
- 新增 **SQLAlchemy + SQLite 持久化层**：`benchmark` / `eval_run` / `case_result` 三张表，关键指标规范化为可查询标量列，完整明细存 JSON 列；通过 `DATABASE_URL` 可切换 PostgreSQL。
- 新增 **benchmark 库**：支持上传与现有 `cases/` 同格式的 YAML 用例集，用现有 `loader.py` 校验、命名、版本化、重复选用；内置 `cases/breast_cancer` 注册为 builtin benchmark。
- 新增 **评测任务调度**：`JobRunner` 抽象 + 进程内 asyncio 实现（并发上限、运行状态机、失败落 `error_msg`），未来可替换为外部队列而不改业务代码。
- 发起评测时可配置**评测打分模型**（LLM-as-Judge / scoring_point 的 provider / model / base_url / api_key），现为 gpt，未来可换更强模型；被测 bot 沿用服务器 `config.yaml` 的 adapter（可选覆盖）。
- 新增 **React + Ant Design 前端**：benchmark 管理、发起评测、评测列表（实时进度）、单次评测看板、用例结果列表与明细页、跨 run 趋势看板。
- 评测跑完**双写兼容**：既落库、也按现有规则写 `outputs/<slug>/report.json`，CLI 与平台互不影响。
- 现阶段**不引入登录鉴权**（单人使用），仅在数据模型与架构上为多人并发预留。

## Capabilities

### New Capabilities

- `eval-platform-service`: 评测平台后端服务能力——评测结果与 benchmark 的持久化存储、benchmark 库管理、评测任务调度与状态跟踪、对外 REST API。
- `eval-platform-dashboard`: 评测平台前端能力——基于数据库数据呈现聚合看板、跨 run 趋势、单条用例报告明细，并提供 benchmark 管理与发起评测的交互入口。

### Modified Capabilities

<!-- 本次为纯叠加层，不改动现有 judging-pipeline / reporting / dialog-runner 等能力的 requirement，故无 Modified Capabilities。 -->

## Impact

- 新增代码：`server/`（FastAPI 后端）、`frontend/`（Vite + React + TS + Ant Design）。
- 新增依赖：`pyproject.toml` 增加 `[project.optional-dependencies].server`（`fastapi` / `uvicorn` / `sqlalchemy` / `aiosqlite` / `python-multipart`）；前端独立 `frontend/package.json`。
- 新增运行期产物：SQLite 数据库文件（默认本地）、`uploads/benchmarks/<id>/` 上传用例存储目录。
- 复用但不修改：`medeval/service.py`、`medeval/judges/**`、`medeval/reporter/**`、`medeval/models.py` 等判分与报告核心（不触碰 `TestCase` / `BaseJudge` / `FailureTag` 与 HardGate 治理逻辑）。
- 现有 CLI（`medeval run` 等）行为不变。
