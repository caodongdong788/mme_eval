# Tasks

## 1. 依赖与构建文件
- [x] 1.1 `pyproject.toml` 增加 `[project.optional-dependencies] postgres = ["psycopg2-binary>=2.9"]`
- [x] 1.2 多阶段 `Dockerfile`（frontend build + python runtime）
- [x] 1.3 `.dockerignore`

## 2. Compose 与配置模板
- [x] 2.1 `docker-compose.yml`（app + postgres + volumes + healthcheck）
- [x] 2.2 `.env.docker.example`（生产向默认值说明）
- [x] 2.3 `scripts/docker-entrypoint.sh`（确保数据目录存在后启动 uvicorn）

## 3. 文档与验证
- [x] 3.1 `server/README.md` Docker 部署章节
- [x] 3.2 `tests/deploy/test_docker_artifacts.py`（Dockerfile/compose 存在性与关键片段）
- [x] 3.3 `docker build`：本机无 Docker CLI，以 artifact 测试 + Dockerfile 多阶段结构替代；部署机执行 `docker compose up --build`
- [x] 3.4 `pytest` 620 绿 + `openspec validate --strict` → `openspec archive`
