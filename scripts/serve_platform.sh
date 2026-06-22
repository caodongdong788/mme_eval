#!/usr/bin/env bash
# 生产式启动：构建前端（若有改动）→ 由 FastAPI 静态托管 + 提供 API。
# 用法：scripts/serve_platform.sh [--port 8000] [--skip-build]
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=8000
SKIP_BUILD=0
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --skip-build) SKIP_BUILD=1; shift;;
    *) ARGS+=("$1"); shift;;
  esac
done

PY=".venv/bin/python"
[[ -x "$PY" ]] || PY="python"

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  echo "[serve] 构建前端 ..."
  (cd frontend && npm install --silent && npm run build)
fi

echo "[serve] 启动后端（含前端静态托管）于 http://localhost:${PORT}"
exec "$PY" -m uvicorn server.app:app --host 0.0.0.0 --port "${PORT}" ${ARGS[@]+"${ARGS[@]}"}
