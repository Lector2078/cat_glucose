# Cat Glucose Tracker — CLAUDE.md

## Project Summary
Single-household web app to track glucose readings for one or more cats. Supports manual entry, file import (CSV/XLSX/TXT), and Metabase analytics dashboards. Designed for self-hosting on a VPS or locally via Docker Compose.

## Tech Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, psycopg3, Pydantic v2
- **Frontend**: Vanilla JS + HTML/CSS (static, served by FastAPI)
- **DB**: PostgreSQL 16 (SQLite fallback via `DATABASE_URL`)
- **Analytics**: Metabase v0.53.4
- **Infra**: Docker Compose, Caddy 2.9 (prod reverse proxy with auto-HTTPS)
- **File parsing**: openpyxl for XLSX; stdlib csv for CSV; custom line parser for TXT

## Project Structure
```
api/          FastAPI app (main.py, models.py, schemas.py, importers.py, auth.py, database.py)
frontend/     Static UI (index.html, assets/app.js, assets/styles.css)
infra/        docker-compose.yml, docker-compose.prod.yml, Dockerfile.web, Caddyfile
metabase/     starter_queries.sql, dashboard_setup.md
scripts/      backup_postgres.sh, restore_postgres.sh
testing_data/ cat_glucose_21-11-2024.csv (FreeStyle Libre 2 export)
```

## Active Features
- Session-based auth (single household user, cookie, 24h TTL, in-memory session store)
- Cat CRUD with cascade delete of readings
- Manual glucose reading entry (mg/dL, with context/notes)
- File import: preview → column mapping → commit
  - Detects CSV header row (handles FreeStyle Libre 2 metadata rows)
  - Handles mmol/L → mg/dL conversion automatically
  - FreeStyle Libre fallback column resolution (`Historic Glucose mmol/L`, `Scan Glucose mmol/L`, `Strip Glucose mmol/L`)
  - Dedup via `uq_dedup_reading` unique constraint (cat_id, reading_at, glucose_value)
  - Import job tracking with per-row error reports (CSV download)
- Rate limiting (in-memory sliding window, 60 req/min default, separate buckets for login/import)
- Metabase bootstrap SQL endpoint (`/api/metabase/bootstrap`)
- Health endpoint: `/healthz`

## Auth
- Credentials from env: `HOUSEHOLD_USERNAME`, `HOUSEHOLD_PASSWORD`
- Session cookie: `cat_glucose_session` (httponly, samesite=lax)
- `secure=False` currently — needs to be `True` in prod behind Caddy HTTPS

## Data Model
- `cats`: id, name (unique), birth_date, notes, created_at
- `glucose_readings`: id, cat_id (FK), reading_at, glucose_value, unit, context, notes, source (manual|import), created_at; unique on (cat_id, reading_at, glucose_value)
- `import_jobs`: id, filename, format, status (pending|completed|failed), rows_total/inserted/rejected, error_report_path, created_at
- `import_rows`: id, import_job_id (FK), raw_payload (JSON str), parse_status (accepted|rejected), error_reason, created_at

## Code Style & Conventions
- All backend: typed with Python type hints; SQLAlchemy `Mapped[]` columns
- Pydantic schemas in `schemas.py`; ORM models in `models.py`
- Route handlers in `main.py` (monolithic for now — acceptable at this scale)
- Importers are pure functions in `importers.py` (no DB access)
- Frontend: no framework, direct DOM manipulation, `api()` / `apiForm()` fetch wrappers
- Env vars consumed directly via `os.getenv()` with defaults
- Error reports written to `data/import-errors/` (created at startup)

## Known Issues / TODOs
- `secure=False` on session cookie — should be env-driven (`True` in prod)
- Sessions stored in-memory (`_sessions` dict in `auth.py`) — lost on restart; no logout endpoint
- No logout route exposed in the UI
- `datetime.utcnow()` used in models — deprecated in Python 3.12; should use `datetime.now(timezone.utc)`
- Rate limiter is per-process in-memory; won't work correctly with multiple workers
- No pagination on `/api/readings` — could get slow with large datasets
- FreeStyle Libre CSV Record Type 6 rows (app/sensor events with no glucose) are imported and fail gracefully but add noise to rejected rows count
- `suggest_import_columns` only matches specific column name patterns — may miss novel export formats

## Import Format Notes
- FreeStyle Libre 2 CSV: row 1 is metadata, row 2 is header — `_find_csv_header_idx` handles this
- Record Type 0 = historic glucose, Type 1 = scan glucose, Type 6 = events (no glucose value)
- mmol/L columns auto-detected by "mmol" in column name and multiplied by 18.0182
- TXT: one reading per line, `timestamp,value` or `timestamp value`

## Environment Variables
```
APP_DOMAIN, METABASE_DOMAIN
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, DATABASE_URL
HOUSEHOLD_USERNAME, HOUSEHOLD_PASSWORD, SESSION_SECRET (unused currently)
RATE_LIMIT_PER_MINUTE (default 60)
MB_DB_TYPE, MB_DB_DBNAME, MB_DB_PORT, MB_DB_USER, MB_DB_PASS, MB_DB_HOST
```

## Deployment
- Local: `docker compose --env-file .env -f infra/docker-compose.yml up -d --build`
- Prod: add `-f infra/docker-compose.prod.yml` (Caddy handles TLS, ports 80/443 only)
- DB volume: `postgres_data`; wipe with `down -v`

## Metabase Starter Queries (in metabase/starter_queries.sql)
- Daily avg by cat, 7d/30d moving avg, weekly min/max/median, time-of-day pattern

## Contour Next GEN / glucometerutils Support (added)
Two new import formats handled transparently in `importers.py`:

### glucometerutils `dump` output
- **No header row**, 4 comma-separated fields per line: `timestamp, glucose_value, meal, comment`
- Example: `2024-11-21 08:32:00,245,Before Meal,`
- Detection: `_is_glucometerutils_dump()` — first data line has no header keywords and field[1] is numeric
- Synthetic column names injected: `Timestamp`, `Glucose Value`, `Meal`, `Comment`
- Auto-suggests `Timestamp` → datetime col, `Glucose Value` → glucose col
- **Unit heuristic in `parse_glucose_value()`**: if value < 35 AND no "mmol" in column name → treated as mmol/L and converted. Covers meters set to mmol/L where glucometerutils outputs no unit marker.
- How to produce: `glucometer --driver contourusb dump > readings.csv` (Contour Next GEN uses `contourusb` driver)

### Contour Diabetes App CSV (`ContourCSVReport_*.csv`)
- Exported from: Contour app → My Care → Reports → CSV
- BOM-prefixed UTF-8; has header row
- EN headers: `#, Date and Time, Readings [mg/dL], Meal Marker, Data Source, Notes, ...`
- DE headers: `#, Datum und Zeit, Messungen [mg/dL], Mahlzeit-Markierung, ...`
- Date formats: `MM/DD/YY HH:MM` (EN) or `DD.MM.YY HH:MM` (DE) — both handled in `_DATETIME_FORMATS`
- Detection: `_is_contour_app_csv()` — header contains "date and time"/"datum und zeit" + "readings"/"messungen"
- Rows with empty `Readings` field (meal/insulin-only entries) are skipped in `_parse_contour_app_csv()`
- Normalised to same synthetic column names as glucometerutils so `suggest_import_columns` picks them up identically
