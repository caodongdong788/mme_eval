#!/usr/bin/env bash
# Docker 入口：确保持久化目录存在，再 exec 主进程（不改变 CMD 语义）。
set -euo pipefail

mkdir -p "${MEDEVAL_OUTPUTS_DIR:-/data/outputs}" "${MEDEVAL_UPLOADS_DIR:-/data/uploads/benchmarks}"

exec "$@"
