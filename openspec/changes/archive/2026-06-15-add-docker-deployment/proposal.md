# Proposal: Docker 化部署（MME 评测平台）

## Why

平台目前仅提供 `scripts/serve_platform.sh` 裸机启动，上云需手工装 Python/Node、配环境、管持久化目录。Docker 化后一次 `docker compose up` 即可复现运行环境，便于公网/内网部署与迁移。

## What Changes

- 新增多阶段 `Dockerfile`：构建前端 `dist` + 安装 Python 平台依赖，单容器由 uvicorn 托管 API 与静态前端。
- 新增 `docker-compose.yml`：`app` + `postgres`（健康检查 + volume 持久化 `outputs`/`uploads`/DB）。
- 新增 `.dockerignore`、`.env.docker.example`、可选 `scripts/docker-entrypoint.sh`。
- `pyproject.toml` 增加可选依赖 `postgres`（`psycopg2-binary`），供 Compose 连接 Postgres。
- `server/README.md` 补充 Docker 部署章节（构建、环境变量、volume、HTTPS 前置说明）。

## Non-Goals

- 不引入 K8s / 外部队列（`JobRunner` 仍进程内，**单实例**部署）。
- 不改判分/评测业务逻辑。
- 不在镜像内 baked 生产密钥（`.env` / `config.yaml` 由挂载或 `env_file` 注入）。

## Risks

- 镜像体积（含 Node 构建阶段）；多阶段可控制 runtime 层大小。
- SQLite 单机模式仍可用，但 Compose 默认走 Postgres（生产推荐）。
