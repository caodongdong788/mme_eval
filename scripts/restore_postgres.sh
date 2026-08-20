#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 || "${MME_CONFIRM_RESTORE:-}" != "RESTORE" ]]; then
  echo "Usage: MME_CONFIRM_RESTORE=RESTORE scripts/restore_postgres.sh /absolute/path/mme-*.dump" >&2
  exit 2
fi

BACKUP_FILE="$1"
if [[ "$BACKUP_FILE" != /* || ! -s "$BACKUP_FILE" || "$BACKUP_FILE" != *.dump ]]; then
  echo "Restore target must be an existing absolute .dump file" >&2
  exit 2
fi
if [[ -f "$BACKUP_FILE.sha256" ]]; then
  (cd "$(dirname "$BACKUP_FILE")" && sha256sum --check "$(basename "$BACKUP_FILE").sha256")
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.release.yml)

RUNNING_SERVICES="$("${COMPOSE[@]}" ps --status running --services)"
if grep -Eq '^(app|worker)$' <<<"$RUNNING_SERVICES"; then
  echo "Stop app and worker before restore: docker compose -f docker-compose.yml -f docker-compose.release.yml stop app worker" >&2
  exit 2
fi

"${COMPOSE[@]}" exec -T db pg_restore \
  --username "${POSTGRES_USER:-medeval}" \
  --dbname "${POSTGRES_DB:-medeval}" \
  --clean --if-exists --no-owner --no-acl --exit-on-error --single-transaction \
  <"$BACKUP_FILE"
echo "Postgres restore completed: $BACKUP_FILE"
