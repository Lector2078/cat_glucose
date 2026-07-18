# Cat Glucose Tracker

A web app for a single household to track one or more cats' glucose readings with manual entry, file import, and Metabase analytics.

## Features
- Household login session auth
- Cat CRUD (create, edit, delete)
- Manual glucose reading entry and listing
- Import from `.csv`, `.xlsx`, and `.txt`
- Import preview, column mapping, dedup protection, and error reports
- Metabase integration with starter SQL dashboards
- Docker Compose local stack with Postgres, API/UI, Metabase, and pgAdmin
- Backup and restore scripts

## Project Structure
- `api/`: FastAPI backend and data model
- `frontend/`: Static UI served by backend
- `infra/`: Docker Compose and deployment checklist
- `metabase/`: Starter SQL and setup guide
- `scripts/`: Backup/restore scripts

## Quick Start (Local)
1. Copy `.1env.example` to `.env` and configure for local development:
   ```bash
   cp .1env.example .env
   ```
2. Build and run:
   ```bash
   docker compose --env-file .env -f infra/docker-compose.yml up -d --build
   ```
3. Open:
   - App: `http://localhost:8000`
   - Metabase: `http://localhost:3000`
   - pgAdmin: `http://localhost:5050` (optional, for database admin)

4. Log in with credentials from `.env`:
   - Username: `HOUSEHOLD_USERNAME`
   - Password: `HOUSEHOLD_PASSWORD`

5. Create your cats and start adding glucose readings via manual entry or import.

## Importing Data
The app supports imports from CSV, XLSX, and TXT files. You'll map columns in the UI during import to specify which columns contain datetime and glucose values.

- **CSV/XLSX**: Map columns in UI for datetime and glucose value.
- **TXT**: Supports lines like:
  - `2026-04-27T08:00:00,245`
  - `2026-04-27T08:00:00 245`

## Common Local Commands
- Recreate from scratch (resets local DB volume):
  ```bash
  docker compose --env-file .env -f infra/docker-compose.yml down -v
  docker compose --env-file .env -f infra/docker-compose.yml up -d --build
  ```
- Check running services:
  ```bash
  docker compose --env-file .env -f infra/docker-compose.yml ps
  ```
- Follow logs:
  ```bash
  docker compose --env-file .env -f infra/docker-compose.yml logs -f web
  docker compose --env-file .env -f infra/docker-compose.yml logs -f postgres
  docker compose --env-file .env -f infra/docker-compose.yml logs -f metabase
  ```
- Test API health:
  ```bash
  curl http://localhost:8000/healthz
  ```

## Production Mode (with Caddy)
Use this mode on a VPS with real DNS names and automatic HTTPS.

1. Copy `.1env.example` to `.env` and set production values:
   ```bash
   cp .1env.example .env
   ```
2. Edit `.env` with:
   - `APP_DOMAIN=app.yourdomain.com`
   - `METABASE_DOMAIN=metabase.yourdomain.com`
   - Strong secrets/passwords for:
     - `HOUSEHOLD_PASSWORD`
     - `POSTGRES_PASSWORD`
     - `SESSION_SECRET`
3. Create DNS `A` records for both domains pointing to your VPS IP.
4. Start using both compose files:
   ```bash
   docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml up -d --build
   ```
5. Open:
   - `https://APP_DOMAIN`
   - `https://METABASE_DOMAIN`

### Production Maintenance Commands
- Stop stack:
  ```bash
  docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml down
  ```
- Check status:
  ```bash
  docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml ps
  ```
- Follow logs:
  ```bash
  docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml logs -f caddy
  docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml logs -f web
  ```

## Database Admin (Local Only)
pgAdmin is included in the local stack for database management. Access it at `http://localhost:5050` with credentials from `.env`:
- Email: `PGADMIN_DEFAULT_EMAIL`
- Password: `PGADMIN_DEFAULT_PASSWORD`

## Metabase Setup
- Follow `metabase/dashboard_setup.md`.
- Use `/api/metabase/bootstrap` to get read-only role SQL.

## Ops
- Health endpoint: `/healthz`
- Nightly backups: `scripts/backup_postgres.sh`
- Restore: `scripts/restore_postgres.sh`
