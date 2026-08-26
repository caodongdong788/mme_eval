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
TARGET_REV="${MME_DEPLOY_COMMIT:-}"
if [[ -z "$TARGET_REV" ]]; then
  # 人工发布也只解析一次远端 HEAD，后续全程使用该不可变提交。
  git fetch --quiet gitlab main
  TARGET_REV="$(git rev-parse FETCH_HEAD)"
else
  git fetch --quiet gitlab main
fi
git cat-file -e "${TARGET_REV}^{commit}"
AFTER_REV="$(git rev-parse "${TARGET_REV}^{commit}")"
if ! git merge-base --is-ancestor "$AFTER_REV" FETCH_HEAD; then
  echo "Refusing to deploy commit outside gitlab/main: $AFTER_REV" >&2
  exit 1
fi
if [[ "$BEFORE_REV" != "$AFTER_REV" ]]; then
  git checkout --detach --quiet "$AFTER_REV"
  # 当前脚本可能已被新提交替换；从目标提交重新执行，避免继续读取旧文件偏移。
  if [[ "${MME_DEPLOY_REEXECUTED:-0}" != "1" ]]; then
    exec env MME_DEPLOY_REEXECUTED=1 MME_DEPLOY_BEFORE_REV="$BEFORE_REV" \
      MME_DEPLOY_COMMIT="$AFTER_REV" bash "$0"
  fi
fi
WORKER_CHANGED=0
DATABASE_CHANGED=0
if [[ "$BEFORE_REV" != "$AFTER_REV" ]] && ! git diff --quiet "$BEFORE_REV" "$AFTER_REV" -- \
  Dockerfile pyproject.toml uv.lock migrations medeval server/worker.py server/durable_queue.py \
  server/durable_jobs.py server/job_specs.py server/jobs.py server/models_db.py \
  server/db.py server/settings.py server/services; then
  WORKER_CHANGED=1
fi
if [[ "$BEFORE_REV" != "$AFTER_REV" ]] && ! git diff --quiet "$BEFORE_REV" "$AFTER_REV" -- \
  migrations server/models_db.py server/db.py scripts/docker-entrypoint.sh; then
  DATABASE_CHANGED=1
fi

OLD_APP_IMAGE=""
OLD_WORKER_IMAGE=""
if APP_CONTAINER_ID="$("${COMPOSE[@]}" ps -q app)" && [[ -n "$APP_CONTAINER_ID" ]]; then
  OLD_APP_IMAGE="$(docker inspect --format '{{.Image}}' "$APP_CONTAINER_ID")"
  docker tag "$OLD_APP_IMAGE" mme-eval:rollback-app
fi
if WORKER_CONTAINER_ID="$("${COMPOSE[@]}" ps -q worker)" && [[ -n "$WORKER_CONTAINER_ID" ]]; then
  OLD_WORKER_IMAGE="$(docker inspect --format '{{.Image}}' "$WORKER_CONTAINER_ID")"
  docker tag "$OLD_WORKER_IMAGE" mme-eval:rollback-worker
fi

rollback_app() {
  if [[ -z "$OLD_APP_IMAGE" ]]; then
    return
  fi
  export MME_IMAGE_TAG=rollback-app
  if ! "${COMPOSE[@]}" up -d --no-deps --no-build app; then
    echo "MME rollback warning: previous app image could not be started" >&2
    return 0
  fi
  for _ in $(seq 1 12); do
    curl -fsS http://127.0.0.1:"${MME_PORT:-8000}"/api/health >/dev/null && return
    sleep 2
  done
  echo "MME rollback warning: previous app image did not become healthy" >&2
  return 0
}

rollback_worker() {
  if [[ -z "$OLD_WORKER_IMAGE" ]]; then
    return
  fi
  export MME_IMAGE_TAG=rollback-worker
  if ! "${COMPOSE[@]}" up -d --no-deps --no-build worker; then
    echo "MME rollback warning: previous worker image could not be started" >&2
  fi
  return 0
}

# 数据结构变化时强制创建发布前快照；普通代码发布复用最近的有效快照，避免每次重复
# 导出完整数据库。可用 always/skip 显式覆盖，普通发布默认至多每天备份一次。
BACKUP_MODE="${MME_DEPLOY_BACKUP_MODE:-auto}"
BACKUP_MAX_AGE_S="${MME_DEPLOY_BACKUP_MAX_AGE_S:-86400}"
case "$BACKUP_MODE" in
  always)
    scripts/backup_postgres.sh
    ;;
  skip)
    echo "Postgres pre-deploy backup skipped by MME_DEPLOY_BACKUP_MODE=skip"
    ;;
  auto)
    if [[ "$DATABASE_CHANGED" == "1" ]]; then
      echo "Database-sensitive changes detected; creating a fresh pre-deploy backup"
      scripts/backup_postgres.sh
    else
      scripts/backup_postgres.sh --if-stale "$BACKUP_MAX_AGE_S"
    fi
    ;;
  *)
    echo "Invalid MME_DEPLOY_BACKUP_MODE: $BACKUP_MODE (expected auto, always, or skip)" >&2
    exit 2
    ;;
esac

export MME_IMAGE_TAG="$AFTER_REV"
"${COMPOSE[@]}" build app
if ! "${COMPOSE[@]}" up -d --no-deps app; then
  rollback_app
  echo "MME deployment failed: app container could not be started" >&2
  exit 1
fi

HEALTH_INTERVAL_S="${MME_DEPLOY_HEALTH_INTERVAL_S:-2}"
HEALTH_ATTEMPTS="${MME_DEPLOY_HEALTH_ATTEMPTS:-45}"
for _ in $(seq 1 "$HEALTH_ATTEMPTS"); do
  if curl -fsS http://127.0.0.1:"${MME_PORT:-8000}"/api/health >/dev/null; then
    # 默认只保证 Worker 已存在，不重建正在工作的实例，因此普通 Web 发布完全不打断评测。
    # 仅 Worker 代码需要升级时显式传 DEPLOY_WORKER=1；它会优雅释放租约并断点续跑。
    if [[ "${DEPLOY_WORKER:-auto}" == "1" || ( "${DEPLOY_WORKER:-auto}" == "auto" && "$WORKER_CHANGED" == "1" ) ]]; then
      if ! "${COMPOSE[@]}" up -d --no-deps worker; then
        rollback_worker
        rollback_app
        echo "MME deployment failed: worker container could not be started" >&2
        exit 1
      fi
    else
      if ! "${COMPOSE[@]}" up -d --no-deps --no-recreate worker; then
        rollback_worker
        rollback_app
        echo "MME deployment failed: existing worker could not be retained" >&2
        exit 1
      fi
    fi
    for _ in $(seq 1 10); do
      if "${COMPOSE[@]}" ps --status running --services | grep -qx worker; then
        break
      fi
      sleep 1
    done
    if ! "${COMPOSE[@]}" ps --status running --services | grep -qx worker; then
      "${COMPOSE[@]}" logs --tail=100 worker >&2
      rollback_worker
      rollback_app
      echo "MME deployment failed: worker is not running" >&2
      exit 1
    fi
    for _ in $(seq 1 12); do
      WORKER_CONTAINER_ID="$("${COMPOSE[@]}" ps -q worker)"
      if [[ -n "$WORKER_CONTAINER_ID" ]] && \
        [[ "$(docker inspect --format '{{.State.Health.Status}}' "$WORKER_CONTAINER_ID")" == "healthy" ]]; then
        break
      fi
      sleep 2
    done
    WORKER_CONTAINER_ID="$("${COMPOSE[@]}" ps -q worker)"
    if [[ -z "$WORKER_CONTAINER_ID" ]] || \
      [[ "$(docker inspect --format '{{.State.Health.Status}}' "$WORKER_CONTAINER_ID")" != "healthy" ]]; then
      "${COMPOSE[@]}" logs --tail=100 worker >&2
      rollback_worker
      rollback_app
      echo "MME deployment failed: worker readiness check failed" >&2
      exit 1
    fi
    # 护士端评分由归一化 15 分调整为原始 10 分后，发布时一次性重算已完成
    # Agent 八维 Run。每个 Run 自带评分版本标记，后续发布会快速跳过。
    # 若迁移异常，保留新应用运行以便修复后断点重试，避免旧应用按旧分制展示
    # 已部分更新的数据；本次发布仍以失败退出，方便流水线明确告警。
    if ! "${COMPOSE[@]}" exec -T app python -m server.score_recalibration; then
      "${COMPOSE[@]}" logs --tail=100 app >&2
      echo "MME deployment failed: historical score recalibration needs retry" >&2
      exit 1
    fi
    "${COMPOSE[@]}" ps
    echo "MME deployment succeeded: $(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep "$HEALTH_INTERVAL_S"
done

"${COMPOSE[@]}" logs --tail=100 app >&2
if [[ -n "$OLD_APP_IMAGE" ]]; then
  rollback_app
  echo "MME deployment rolled back to the previous app image" >&2
fi
echo "MME deployment health check failed" >&2
exit 1
