# VPS Setup Checklist

## Base Setup
- Create a low-cost VPS and point DNS:
  - `APP_DOMAIN` -> VPS IP
  - `METABASE_DOMAIN` -> VPS IP
- Install Docker and Docker Compose plugin.
- Copy `.env.example` to `.env` and set strong secrets.

## Deploy
- Run:
  - `docker compose -f infra/docker-compose.yml build`
  - `docker compose -f infra/docker-compose.yml up -d`
- Validate:
  - `https://APP_DOMAIN/healthz` returns `{"status":"ok"}`
  - `https://METABASE_DOMAIN` shows Metabase login page

## Security
- Use strong household password in `.env`.
- Restrict VPS firewall to `80/443` only.
- Keep system packages and Docker images updated monthly.
- Keep `POSTGRES_PASSWORD` and session secrets out of version control.

## Backup and Restore
- Add nightly cron (example):
  - `0 2 * * * cd /path/to/cat_glucose && ./.env && BACKUP_DIR=./backups ./scripts/backup_postgres.sh`
- Copy backups off-host (S3-compatible bucket).
- Test restore weekly using `scripts/restore_postgres.sh`.
