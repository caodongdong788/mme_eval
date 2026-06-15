#!/usr/bin/env bash
# 开发式启动：后端 uvicorn --reload + 前端 Vite dev server（/api 自动代理到后端）。
# 用法：scripts/dev_platform.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
[[ -x "$PY" ]] || PY="python"

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "[dev] 后端 http://localhost:8000  前端 http://localhost:5173"
"$PY" -m uvicorn server.app:app --reload --port 8000 &
(cd frontend && npm install --silent && npm run dev) &
wait
