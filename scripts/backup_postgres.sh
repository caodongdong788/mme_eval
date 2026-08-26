#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKUP_DIR="${MME_BACKUP_DIR:-$ROOT_DIR/backups/postgres}"
RETENTION_DAYS="${MME_BACKUP_RETENTION_DAYS:-14}"
mkdir -p "$BACKUP_DIR"

MAX_AGE_S=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --if-stale)
      [[ $# -ge 2 ]] || { echo "--if-stale 需要提供秒数" >&2; exit 2; }
      MAX_AGE_S="$2"
      shift 2
      ;;
    *)
      echo "未知参数：$1" >&2
      exit 2
      ;;
  esac
done

if [[ -n "$MAX_AGE_S" ]]; then
  [[ "$MAX_AGE_S" =~ ^[0-9]+$ ]] || { echo "--if-stale 必须是非负整数秒" >&2; exit 2; }
  LATEST_BACKUP=""
  for CANDIDATE in "$BACKUP_DIR"/mme-*.dump; do
    [[ -s "$CANDIDATE" && -s "${CANDIDATE}.sha256" ]] || continue
    if [[ -z "$LATEST_BACKUP" || "$CANDIDATE" -nt "$LATEST_BACKUP" ]]; then
      LATEST_BACKUP="$CANDIDATE"
    fi
  done
  if [[ -n "$LATEST_BACKUP" ]]; then
    NOW_EPOCH="$(date +%s)"
    if stat -c %Y "$LATEST_BACKUP" >/dev/null 2>&1; then
      BACKUP_EPOCH="$(stat -c %Y "$LATEST_BACKUP")"
    else
      BACKUP_EPOCH="$(stat -f %m "$LATEST_BACKUP")"
    fi
    BACKUP_AGE_S="$((NOW_EPOCH - BACKUP_EPOCH))"
    if (( BACKUP_AGE_S <= MAX_AGE_S )); then
      echo "Postgres backup reused: $LATEST_BACKUP (${BACKUP_AGE_S}s old, max ${MAX_AGE_S}s)"
      exit 0
    fi
  fi
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/mme-${STAMP}.dump"
TEMP_TARGET="$TARGET.partial"
trap 'rm -f "$TEMP_TARGET"' EXIT
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.release.yml)

"${COMPOSE[@]}" exec -T db pg_dump \
  --username "${POSTGRES_USER:-medeval}" \
  --dbname "${POSTGRES_DB:-medeval}" \
  --format custom \
  --no-owner \
  --no-acl >"$TEMP_TARGET"

test -s "$TEMP_TARGET"
mv "$TEMP_TARGET" "$TARGET"
trap - EXIT
(cd "$BACKUP_DIR" && sha256sum "$(basename "$TARGET")" >"$(basename "$TARGET").sha256")
find "$BACKUP_DIR" -type f -name 'mme-*.dump*' -mtime "+$RETENTION_DAYS" -delete
echo "Postgres backup created: $TARGET"
