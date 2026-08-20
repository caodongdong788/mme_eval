#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKUP_DIR="${MME_BACKUP_DIR:-$ROOT_DIR/backups/postgres}"
RETENTION_DAYS="${MME_BACKUP_RETENTION_DAYS:-14}"
mkdir -p "$BACKUP_DIR"

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
