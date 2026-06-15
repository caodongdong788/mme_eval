# syntax=docker/dockerfile:1
# MME · Agent 评测平台 — 多阶段镜像：构建前端 + 运行 FastAPI（静态托管 + API）。

# --- Stage 1: 前端构建 ---
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python 运行时 ---
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖描述与源码，再安装（利于层缓存）
COPY pyproject.toml README.md ./
COPY medeval/ medeval/
COPY server/ server/
COPY cases/ cases/
COPY config.yaml ./config.yaml

COPY --from=frontend-build /frontend/dist frontend/dist/

RUN pip install -e ".[server,llm-openai,langfuse,postgres]"

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
