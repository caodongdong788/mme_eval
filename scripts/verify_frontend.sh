#!/usr/bin/env bash
# 前端规范门禁（与 .cursor/rules/frontend-workflow.mdc 对齐）
set -euo pipefail
cd "$(dirname "$0")/../frontend"
npm run verify
