# Cat Glucose Tracker

A web app for a single household to track one or more cats' glucose readings with manual entry, file import, and Metabase analytics.

## Features
- Household login session auth
- Cat CRUD (create, edit, delete)
- Manual glucose reading entry and listing
- Import from `.csv`, `.xlsx`, and `.txt`
- Import preview, column mapping, dedup protection, and error reports
- Metabase integration with starter SQL dashboards
- Docker Compose local stack with Postgres, API/UI, and Metabase
- Backup and restore scripts

## Project Structure
- `api/`: FastAPI backend and data model
- `frontend/`: Static UI served by backend
- `infra/`: Docker Compose and deployment checklist
- `metabase/`: Starter SQL and setup guide
- `scripts/`: Backup/restore scripts

## Quick Start (Local)
1. Copy `.env.example` to `.env` and set secure values.
2. Build and run with the root env file:
   - `docker compose --env-file .env -f infra/docker-compose.yml up -d --build`
3. Open:
   - App: `http://localhost:8000`
   - Metabase: `http://localhost:3000`

## Common Local Commands
- Recreate from scratch (resets local DB volume):
  - `docker compose --env-file .env -f infra/docker-compose.yml down -v`
  - `docker compose --env-file .env -f infra/docker-compose.yml up -d --build`
- Check running services:
  - `docker compose --env-file .env -f infra/docker-compose.yml ps`
- Follow logs:
  - `docker compose --env-file .env -f infra/docker-compose.yml logs -f web`
  - `docker compose --env-file .env -f infra/docker-compose.yml logs -f postgres`
  - `docker compose --env-file .env -f infra/docker-compose.yml logs -f metabase`
- Test API health:
  - `http://localhost:8000/healthz`

## Production Mode (with Caddy)
Use this mode on a VPS with real DNS names and automatic HTTPS.

1. Set production values in `.env`:
   - `APP_DOMAIN=app.yourdomain.com`
   - `METABASE_DOMAIN=metabase.yourdomain.com`
   - strong secrets/passwords for DB and household login
2. Create DNS `A` records for both domains pointing to your VPS IP.
3. Start using both compose files:
   - `docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml up -d --build`
4. Open:
   - `https://APP_DOMAIN`
   - `https://METABASE_DOMAIN`

### Production Maintenance Commands
- Stop stack:
  - `docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml down`
- Check status:
  - `docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml ps`
- Follow logs:
  - `docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml logs -f caddy`
  - `docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml logs -f web`

## Household Login
- Username/password come from `.env`:
  - `HOUSEHOLD_USERNAME`
  - `HOUSEHOLD_PASSWORD`

## Import Format Notes
- CSV/XLSX: map columns in UI for datetime and glucose value.
- TXT: supports lines like:
  - `2026-04-27T08:00:00,245`
  - `2026-04-27T08:00:00 245`

## Metabase Setup
- Follow `metabase/dashboard_setup.md`.
- Use `/api/metabase/bootstrap` to get read-only role SQL.

## Ops
- Health endpoint: `/healthz`
- Nightly backups: `scripts/backup_postgres.sh`
- Restore: `scripts/restore_postgres.sh`
