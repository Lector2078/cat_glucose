# Cat Glucose Tracker

A web app for a single household to track one or more cats' glucose readings with manual entry, file import, and Metabase analytics.

## Features
- Household login session auth
- Cat CRUD (create, edit, delete)
- Manual glucose reading entry and listing
- Import from `.csv`, `.xlsx`, and `.txt`
- Import preview, column mapping, dedup protection, and error reports
- Metabase integration with starter SQL dashboards
- Docker Compose stack with Postgres, Caddy, and Metabase
- Backup and restore scripts

## Project Structure
- `api/`: FastAPI backend and data model
- `frontend/`: Static UI served by backend
- `infra/`: Docker Compose, Caddy, deployment checklist
- `metabase/`: Starter SQL and setup guide
- `scripts/`: Backup/restore scripts

## Quick Start
1. Copy `.env.example` to `.env` and set secure values.
2. Build and run:
   - `docker compose -f infra/docker-compose.yml build`
   - `docker compose -f infra/docker-compose.yml up -d`
3. Open:
   - App: `https://APP_DOMAIN`
   - Metabase: `https://METABASE_DOMAIN`

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
