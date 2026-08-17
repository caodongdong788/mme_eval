#!/usr/bin/env bash
# MME 单机生产部署：单个 Web 容器原地替换，再按需滚动 Worker；任务由数据库租约自动续跑。
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 所有入口（GitLab CI 与人工 SSH）都执行此脚本。用主机锁串行化 Docker 重建，
# 避免两个部署同时 recreate 同名容器而产生 name conflict。
DEPLOY_LOCK_FILE="${MME_DEPLOY_LOCK_FILE:-/var/lock/mme_eval_deploy.lock}"
DEPLOY_LOCK_TIMEOUT_S="${MME_DEPLOY_LOCK_TIMEOUT_S:-900}"
mkdir -p "$(dirname "$DEPLOY_LOCK_FILE")"
exec 9>"$DEPLOY_LOCK_FILE"
if ! flock -w "$DEPLOY_LOCK_TIMEOUT_S" 9; then
  echo "MME deployment lock timeout after ${DEPLOY_LOCK_TIMEOUT_S}s; another deployment is still running" >&2
  exit 1
fi

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.release.yml)

BEFORE_REV="${MME_DEPLOY_BEFORE_REV:-$(git rev-parse HEAD)}"
if [[ -n "${MME_DEPLOY_AFTER_REV:-}" ]]; then
  AFTER_REV="$MME_DEPLOY_AFTER_REV"
else
  git pull --ff-only
  AFTER_REV="$(git rev-parse HEAD)"
  # git pull 可能更新当前正在执行的脚本。Bash 会按文件偏移继续读取，导致新脚本尾部
  # 被跳过；检测到自身变化时从新版本重新执行，并保留用于判断 Worker 变更的版本范围。
  if [[ "$BEFORE_REV" != "$AFTER_REV" ]] && ! git diff --quiet "$BEFORE_REV" "$AFTER_REV" -- scripts/deploy_release.sh; then
    exec env MME_DEPLOY_BEFORE_REV="$BEFORE_REV" MME_DEPLOY_AFTER_REV="$AFTER_REV" bash "$0"
  fi
fi
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
    for _ in $(seq 1 10); do
      if "${COMPOSE[@]}" ps --status running --services | grep -qx worker; then
        break
      fi
      sleep 1
    done
    if ! "${COMPOSE[@]}" ps --status running --services | grep -qx worker; then
      "${COMPOSE[@]}" logs --tail=100 worker >&2
      echo "MME deployment failed: worker is not running" >&2
      exit 1
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
