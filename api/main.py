import csv
import io
import os
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import issue_session, require_auth, verify_credentials
from .database import Base, engine, get_db
from .importers import detect_format, normalize_datetime, parse_csv, parse_txt, parse_xlsx, row_to_string
from .models import Cat, GlucoseReading, ImportJob, ImportRow, ImportStatus, ParseStatus, ReadingSource
from .schemas import CatCreate, CatRead, ImportJobRead, LoginRequest, ReadingCreate, ReadingRead


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cat Glucose Tracker")
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
error_reports_dir = Path(__file__).resolve().parent.parent / "data" / "import-errors"
error_reports_dir.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_rate_buckets: dict[str, deque[float]] = defaultdict(deque)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))


def _check_rate_limit(bucket_key: str) -> None:
    now = time.time()
    bucket = _rate_buckets[bucket_key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    bucket.append(now)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response) -> dict[str, str]:
    _check_rate_limit("login")
    if not verify_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    issue_session(response)
    return {"status": "ok"}


@app.get("/api/auth/me")
def me(_: None = Depends(require_auth)) -> dict[str, bool]:
    return {"authenticated": True}


@app.get("/api/cats", response_model=list[CatRead])
def list_cats(db: Session = Depends(get_db), _: None = Depends(require_auth)) -> list[Cat]:
    return db.scalars(select(Cat).order_by(Cat.name.asc())).all()


@app.post("/api/cats", response_model=CatRead)
def create_cat(payload: CatCreate, db: Session = Depends(get_db), _: None = Depends(require_auth)) -> Cat:
    cat = Cat(name=payload.name.strip(), birth_date=payload.birth_date, notes=payload.notes)
    db.add(cat)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Cat name already exists") from exc
    db.refresh(cat)
    return cat


@app.put("/api/cats/{cat_id}", response_model=CatRead)
def update_cat(cat_id: int, payload: CatCreate, db: Session = Depends(get_db), _: None = Depends(require_auth)) -> Cat:
    cat = db.get(Cat, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Cat not found")
    cat.name = payload.name.strip()
    cat.birth_date = payload.birth_date
    cat.notes = payload.notes
    db.commit()
    db.refresh(cat)
    return cat


@app.delete("/api/cats/{cat_id}", status_code=204)
def delete_cat(cat_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)) -> None:
    cat = db.get(Cat, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Cat not found")
    db.delete(cat)
    db.commit()


@app.get("/api/readings", response_model=list[ReadingRead])
def list_readings(
    cat_id: int | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> list[GlucoseReading]:
    query = select(GlucoseReading).order_by(GlucoseReading.reading_at.desc())
    if cat_id is not None:
        query = query.where(GlucoseReading.cat_id == cat_id)
    if start is not None:
        query = query.where(GlucoseReading.reading_at >= start)
    if end is not None:
        query = query.where(GlucoseReading.reading_at <= end)
    return db.scalars(query).all()


@app.post("/api/readings", response_model=ReadingRead)
def create_reading(payload: ReadingCreate, db: Session = Depends(get_db), _: None = Depends(require_auth)) -> GlucoseReading:
    cat = db.get(Cat, payload.cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Cat not found")
    reading = GlucoseReading(
        cat_id=payload.cat_id,
        reading_at=payload.reading_at,
        glucose_value=payload.glucose_value,
        unit=payload.unit,
        context=payload.context,
        notes=payload.notes,
        source=ReadingSource.import_file if payload.source == "import" else ReadingSource.manual,
    )
    db.add(reading)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate reading") from exc
    db.refresh(reading)
    return reading


@app.delete("/api/readings/{reading_id}", status_code=204)
def delete_reading(reading_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)) -> None:
    reading = db.get(GlucoseReading, reading_id)
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    db.delete(reading)
    db.commit()


def _extract_parsed_rows(file_format: str, content: bytes) -> list[dict[str, Any]]:
    if file_format == "csv":
        return parse_csv(content)
    if file_format == "xlsx":
        return parse_xlsx(content)
    if file_format == "txt":
        return parse_txt(content)
    raise ValueError("Unsupported format")


@app.post("/api/import/preview")
async def preview_import(
    file: UploadFile = File(...),
    max_rows: int = Query(default=25, ge=1, le=250),
    _: None = Depends(require_auth),
) -> dict[str, Any]:
    _check_rate_limit("import")
    content = await file.read()
    file_format = detect_format(file.filename or "")
    rows = _extract_parsed_rows(file_format, content)
    columns = sorted({k for row in rows for k in row.keys()})
    return {
        "filename": file.filename,
        "format": file_format,
        "row_count": len(rows),
        "columns": columns,
        "preview": rows[:max_rows],
    }


@app.post("/api/import/commit", response_model=ImportJobRead)
async def commit_import(
    cat_id: int = Query(...),
    datetime_column: str = Query(...),
    glucose_column: str = Query(...),
    context_column: str | None = Query(default=None),
    notes_column: str | None = Query(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> ImportJob:
    _check_rate_limit("import")
    if not db.get(Cat, cat_id):
        raise HTTPException(status_code=404, detail="Cat not found")

    content = await file.read()
    file_format = detect_format(file.filename or "")
    rows = _extract_parsed_rows(file_format, content)

    job = ImportJob(filename=file.filename or "unknown", format=file_format, status=ImportStatus.pending)
    db.add(job)
    db.flush()

    inserted = 0
    rejected = 0
    error_rows: list[dict[str, str]] = []

    for row in rows:
        raw_payload = row_to_string(row)
        try:
            dt_raw = row.get(datetime_column)
            glucose_raw = row.get(glucose_column)
            if dt_raw is None or glucose_raw is None:
                raise ValueError("Missing required mapped columns")

            reading = GlucoseReading(
                cat_id=cat_id,
                reading_at=normalize_datetime(str(dt_raw)),
                glucose_value=float(glucose_raw),
                unit="mg/dL",
                context=str(row.get(context_column, "")).strip() or None if context_column else None,
                notes=str(row.get(notes_column, "")).strip() or None if notes_column else None,
                source=ReadingSource.import_file,
            )
            db.add(reading)
            db.flush()
            db.add(ImportRow(import_job_id=job.id, raw_payload=raw_payload, parse_status=ParseStatus.accepted))
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            db.add(job)
            db.flush()
            db.add(
                ImportRow(
                    import_job_id=job.id,
                    raw_payload=raw_payload,
                    parse_status=ParseStatus.rejected,
                    error_reason=str(exc),
                )
            )
            error_rows.append({"raw_payload": raw_payload, "error": str(exc)})
            rejected += 1

    job.rows_total = len(rows)
    job.rows_inserted = inserted
    job.rows_rejected = rejected
    job.status = ImportStatus.completed if rejected == 0 else ImportStatus.failed

    if error_rows:
        report_file = error_reports_dir / f"import-job-{job.id}-errors.csv"
        with report_file.open("w", newline="", encoding="utf-8") as report:
            writer = csv.DictWriter(report, fieldnames=["raw_payload", "error"])
            writer.writeheader()
            writer.writerows(error_rows)
        job.error_report_path = str(report_file)

    db.commit()
    db.refresh(job)
    return job


@app.get("/api/import/jobs", response_model=list[ImportJobRead])
def list_import_jobs(db: Session = Depends(get_db), _: None = Depends(require_auth)) -> list[ImportJob]:
    return db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc())).all()


@app.get("/api/import/jobs/{job_id}/errors")
def download_import_errors(job_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)) -> FileResponse:
    job = db.get(ImportJob, job_id)
    if not job or not job.error_report_path:
        raise HTTPException(status_code=404, detail="Error report not found")
    return FileResponse(job.error_report_path, filename=Path(job.error_report_path).name)


@app.get("/api/metabase/bootstrap")
def metabase_bootstrap(_: None = Depends(require_auth)) -> dict[str, str]:
    db_name = os.getenv("POSTGRES_DB", "cat_glucose")
    db_user = os.getenv("POSTGRES_USER", "cat_glucose_user")
    return {
        "read_only_role_sql": (
            "CREATE ROLE metabase_reader LOGIN PASSWORD 'replace_me';\n"
            f"GRANT CONNECT ON DATABASE {db_name} TO metabase_reader;\n"
            "GRANT USAGE ON SCHEMA public TO metabase_reader;\n"
            "GRANT SELECT ON ALL TABLES IN SCHEMA public TO metabase_reader;\n"
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO metabase_reader;\n"
            f"GRANT {db_user} TO metabase_reader;"
        )
    }


if frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets")), name="assets")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(frontend_dir / "index.html")
