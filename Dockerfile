# syntax=docker/dockerfile:1
# MME · Agent 评测平台 — 多阶段镜像：构建前端 + 运行 FastAPI（静态托管 + API）。

# --- Stage 1: 前端构建 ---
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
# Node 20 镜像自带的 npm 10.8 在该 lockfile 上会异常退出（Exit handler never called）；
# npm 11 支持 Node 20.17+，可稳定执行严格的 `npm ci`。
RUN npm install --global npm@11
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python 运行时 ---
FROM python:3.12-slim-bookworm AS runtime

# 生产部署可通过 build arg 切换到就近镜像；开发环境不传该参数时仍使用官方源。
ARG APT_DEBIAN_MIRROR=""
RUN if [ -n "$APT_DEBIAN_MIRROR" ]; then \
      sed -i "s|deb.debian.org/debian|$APT_DEBIAN_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 依赖描述与业务源码分层：通常的代码改动不会再次解析、下载完整依赖。
# 依赖清单由 pyproject 自动导出，避免维护第二份易漂移的 requirements 文件。
COPY pyproject.toml ./
COPY scripts/export_docker_requirements.py /usr/local/bin/export_docker_requirements.py
ARG PIP_INDEX_URL=""
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python /usr/local/bin/export_docker_requirements.py pyproject.toml > /tmp/requirements.production.txt \
    && \
    if [ -n "$PIP_INDEX_URL" ]; then \
      pip install --index-url "$PIP_INDEX_URL" -r /tmp/requirements.production.txt; \
    else \
      pip install -r /tmp/requirements.production.txt; \
    fi

COPY README.md ./
COPY medeval/ medeval/
COPY server/ server/
COPY cases/ cases/
COPY config.yaml ./config.yaml

COPY --from=frontend-build /frontend/dist frontend/dist/

# 仅安装当前项目本身；第三方依赖已在上一层缓存。
RUN pip install --no-deps -e .

COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && useradd --create-home --uid 1000 appuser \
    && mkdir -p /data/outputs /data/uploads/benchmarks \
    && chown -R appuser:appuser /app /data

USER appuser

ENV MEDEVAL_OUTPUTS_DIR=/data/outputs \
    MEDEVAL_UPLOADS_DIR=/data/uploads/benchmarks \
    MEDEVAL_CONFIG_PATH=/app/config.yaml

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
