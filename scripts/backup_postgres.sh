#!/usr/bin/env sh
set -eu

timestamp="$(date +%Y%m%d-%H%M%S)"
backup_dir="${BACKUP_DIR:-./backups}"
mkdir -p "$backup_dir"

docker compose -f infra/docker-compose.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
  > "${backup_dir}/cat_glucose-${timestamp}.sql"

echo "Backup created: ${backup_dir}/cat_glucose-${timestamp}.sql"
