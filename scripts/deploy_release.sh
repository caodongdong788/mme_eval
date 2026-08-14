#!/usr/bin/env bash
# MME 单机生产部署：Web 先无损更新，再滚动 Worker；任务由数据库租约自动续跑。
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.release.yml)

BEFORE_REV="$(git rev-parse HEAD)"
git pull --ff-only
AFTER_REV="$(git rev-parse HEAD)"
WORKER_CHANGED=0
if [[ "$BEFORE_REV" != "$AFTER_REV" ]] && ! git diff --quiet "$BEFORE_REV" "$AFTER_REV" -- \
  Dockerfile pyproject.toml medeval server/worker.py server/durable_queue.py \
  server/durable_jobs.py server/job_specs.py server/jobs.py server/models_db.py \
  server/db.py server/settings.py server/services; then
  WORKER_CHANGED=1
fi
"${COMPOSE[@]}" build app
"${COMPOSE[@]}" up -d --no-deps app

for _ in $(seq 1 18); do
  if curl -fsS http://127.0.0.1:"${MME_PORT:-8000}"/api/health >/dev/null; then
    # 默认只保证 Worker 已存在，不重建正在工作的实例，因此普通 Web 发布完全不打断评测。
    # 仅 Worker 代码需要升级时显式传 DEPLOY_WORKER=1；它会优雅释放租约并断点续跑。
    if [[ "${DEPLOY_WORKER:-auto}" == "1" || ( "${DEPLOY_WORKER:-auto}" == "auto" && "$WORKER_CHANGED" == "1" ) ]]; then
      "${COMPOSE[@]}" up -d --no-deps worker
    else
      "${COMPOSE[@]}" up -d --no-deps --no-recreate worker
    fi
    "${COMPOSE[@]}" ps
    echo "MME deployment succeeded: $(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep 5
done

"${COMPOSE[@]}" logs --tail=100 app >&2
echo "MME deployment health check failed" >&2
exit 1
