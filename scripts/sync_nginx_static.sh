#!/usr/bin/env bash
# 从运行中的 Docker app 容器拷贝 frontend/dist 到 Nginx 可读目录。
# 用法: sudo scripts/sync_nginx_static.sh [/var/www/mme/frontend/dist]
set -euo pipefail

DEST="${1:-/var/www/mme/frontend/dist}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker 未安装" >&2
  exit 1
fi

CID="$(docker compose ps -q app 2>/dev/null || true)"
if [[ -z "$CID" ]]; then
  echo "error: app 容器未运行，请先 docker compose up -d --build" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

docker cp "$CID:/app/frontend/dist/." "$TMP/"
mkdir -p "$DEST"
rsync -a --delete "$TMP/" "$DEST/"

echo "已同步 frontend/dist → $DEST ($(find "$DEST" -type f | wc -l | tr -d ' ') 个文件)"
