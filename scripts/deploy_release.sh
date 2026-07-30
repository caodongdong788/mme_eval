#!/usr/bin/env bash
# MME 单机生产部署：仅重建 app，保留 Postgres 和数据卷。
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.release.yml)

git pull --ff-only
"${COMPOSE[@]}" build app
"${COMPOSE[@]}" up -d --no-deps app

for _ in $(seq 1 18); do
  if curl -fsS http://127.0.0.1:"${MME_PORT:-8000}"/api/health >/dev/null; then
    "${COMPOSE[@]}" ps
    echo "MME deployment succeeded: $(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep 5
done

"${COMPOSE[@]}" logs --tail=100 app >&2
echo "MME deployment health check failed" >&2
exit 1
