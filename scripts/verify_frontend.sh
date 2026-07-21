#!/usr/bin/env bash
# 前端规范门禁（与 AGENTS.md 对齐）
set -euo pipefail
cd "$(dirname "$0")/../frontend"
npm run verify
