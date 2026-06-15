## 1. 后端骨架与依赖

- [x] 1.1 在 `pyproject.toml` 增加 `[project.optional-dependencies].server`（fastapi/uvicorn/sqlalchemy/aiosqlite/python-multipart），并在 `.venv` 安装
- [x] 1.2 新建 `server/` 包：`app.py`（FastAPI 实例 + 路由挂载 + 静态托管前端构建产物）
- [x] 1.3 `server/db.py`：配置化 `DATABASE_URL`（默认 SQLite）的 SQLAlchemy 引擎与会话，启动时 `create_all`

## 2. 持久化层

- [x] 2.1 `server/models_db.py`：定义 ORM 表 `benchmark` / `eval_run` / `case_result`（标量列 + JSON 列，预留 `created_by`）
- [x] 2.2 写表结构/建表测试（建表成功、字段可读写、JSON 列往返）
- [x] 2.3 `server/ingest.py`：`RunReport` → DB 落库器（run 汇总 + 每条 CaseResult 标量列 + detail_json）
- [x] 2.4 TDD：用样例 `RunReport` 验证落库与读回一致（三根通过率轴、分数、稳定性、verdict 无损）

## 3. 评测调度

- [x] 3.1 `server/progress.py`：实现 `ProgressObserver`，把阶段与已完成 case 数写入内存/DB 供查询
- [x] 3.2 `server/jobs.py`：`JobRunner` 抽象 + 进程内 asyncio 实现（并发上限、状态机 pending/running/success/failed、异常落 error_msg）
- [x] 3.3 TDD：覆盖并发执行、成功落库、失败落 error_msg、进度可查询

## 4. benchmark 库

- [x] 4.1 `server/benchmarks.py`：上传 YAML→保存 `uploads/benchmarks/<id>/`→用现有 `load_cases` 校验→写元数据；非法 YAML 拒绝
- [x] 4.2 内置 `cases/breast_cancer` 注册为 `source=builtin` benchmark
- [x] 4.3 TDD：合法上传成功、非法 YAML 被拒、builtin 可见、按 benchmark 解析用例路径

## 5. REST API

- [x] 5.1 `server/schemas.py`：Pydantic 出入参 schema
- [x] 5.2 `server/routers/benchmarks.py`：上传/列表/详情/用例清单/删除
- [x] 5.3 `server/routers/runs.py`：发起评测（选 benchmark + 合并 judge 打分模型覆盖 + 可选 adapter 覆盖 → 建记录 + 启动 JobRunner）/列表/详情/进度/用例列表(筛选)/用例明细
- [x] 5.4 `server/routers/dashboard.py` + `cases.py`：跨 run 趋势、两次 run diff、用例库浏览
- [x] 5.5 接口测试（FastAPI TestClient）覆盖各路由主路径与筛选/错误路径

## 6. 前端基础

- [x] 6.1 `frontend/`：Vite + React + TS + Ant Design + 路由 + axios api client + 图表库(Recharts)，配 dev 代理
- [x] 6.2 benchmark 管理页（上传/列表/查看用例，含上传错误提示）
- [x] 6.3 发起评测页（选 benchmark + 配置打分模型 judge + repeat/tags/limit/run_name）
- [x] 6.4 评测列表页 + 运行中实时进度（轮询）

## 7. 前端看板与明细

- [x] 7.1 单次评测看板（指标卡 + 四模块均分 + 分层级/场景/人群通过率图 + 失败标签分布 + 评级分布 + 延迟 + diff）
- [x] 7.2 用例结果列表（筛选/排序）→ 用例明细页（对话流水、verdict、扣分原因、命中关键词、per-run 稳定性、得分点）
- [x] 7.3 跨 run 趋势看板（通过率/各模块分折线、失败标签趋势）

## 8. 收尾

- [x] 8.1 历史导入工具：扫描 `outputs/*/report.json` 落库（脚本或 CLI 子命令）
- [x] 8.2 启动脚本/文档：一条命令拉起后端 + 托管前端；README 增补平台使用说明
- [x] 8.3 全量 `pytest` 绿 + `medeval run --config config.yaml --dry-run` 验证 + 刷新 Graphify 图谱
- [x] 8.4 `openspec validate --strict` 通过后走 OpenSpec 归档
