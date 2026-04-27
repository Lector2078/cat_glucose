#!/usr/bin/env sh
set -eu

if [ "${1:-}" = "" ]; then
  echo "Usage: scripts/restore_postgres.sh <backup.sql>"
  exit 1
fi

backup_file="$1"
if [ ! -f "$backup_file" ]; then
  echo "Backup file not found: $backup_file"
  exit 1
fi

docker compose -f infra/docker-compose.yml exec -T postgres \
  psql -U "${POSTGRES_USER}" "${POSTGRES_DB}" < "$backup_file"

echo "Restore completed from ${backup_file}"
