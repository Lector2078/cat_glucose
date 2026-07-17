import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

MMOL_L_TO_MG_DL = 18.0182

# FreeStyle Libre fallback columns (mmol/L)
_LIBRE_GLUCOSE_FALLBACK_COLUMNS = (
    "Historic Glucose mmol/L",
    "Scan Glucose mmol/L",
    "Strip Glucose mmol/L",
)

_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    # Contour app EN: MM/DD/YY HH:MM
    "%m/%d/%y %H:%M",
    # Contour app DE: DD.MM.YY HH:MM
    "%d.%m.%y %H:%M",
)

# ---------------------------------------------------------------------------
# Format detection helpers
# ---------------------------------------------------------------------------

def _non_empty_row(row: dict) -> bool:
    return any(str(v).strip() for v in row.values() if v is not None)


def _find_csv_header_idx(lines: list[str]) -> int:
    """Locate the header row in a CSV, handling FreeStyle Libre metadata preamble."""
    for i, line in enumerate(lines[:20]):
        lower = line.lower()
        if "device timestamp" in lower:
            return i
    for i, line in enumerate(lines[:20]):
        lower = line.lower()
        if "timestamp" in lower and "glucose" in lower:
            return i
    for i, line in enumerate(lines[:20]):
        lower = line.lower()
        if any(token in lower for token in ("datetime", "date/time", "reading_at")):
            return i
    return 0


def _is_glucometerutils_dump(lines: list[str]) -> bool:
    """
    glucometerutils dump: no header, each line is:
        <ISO-ish datetime>, <glucose_value>, <meal>, <comment>
    We detect it by: first non-empty line has no recognisable header keywords
    and the second field looks like a number.
    """
    for line in lines[:5]:
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        # If any header-like word appears, it's not a headerless dump
        if any(kw in lower for kw in ("date", "time", "glucose", "reading", "stamp", "#")):
            return False
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            try:
                float(parts[1])
                return True
            except ValueError:
                pass
        return False
    return False


def _is_contour_app_csv(lines: list[str]) -> bool:
    """Contour Diabetes App CSV has a header with 'Date and Time' and 'Readings'."""
    for line in lines[:5]:
        lower = line.lower()
        if ("date and time" in lower or "datum und zeit" in lower) and (
            "readings" in lower or "messungen" in lower
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig", errors="ignore")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    if _is_glucometerutils_dump(lines):
        return _parse_glucometerutils_dump(lines)

    if _is_contour_app_csv(lines):
        return _parse_contour_app_csv(text)

    # Default: FreeStyle Libre / generic CSV
    header_idx = _find_csv_header_idx(lines)
    body = "\n".join(lines[header_idx:])
    stream = io.StringIO(body)
    sample = body[:4096]

    dialect = csv.excel
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        pass

    reader = csv.DictReader(stream, dialect=dialect)
    rows = [dict(row) for row in reader if _non_empty_row(row)]
    if rows:
        return rows

    for delimiter in (";", ",", "\t", "|"):
        stream = io.StringIO(body)
        reader = csv.DictReader(stream, delimiter=delimiter)
        rows = [dict(row) for row in reader if _non_empty_row(row)]
        if len(rows) > 0 and len(rows[0].keys()) > 1:
            return rows
    return []


def _parse_glucometerutils_dump(lines: list[str]) -> list[dict]:
    """
    Parse glucometerutils `glucometer --driver contourusb dump` output.

    Format (no header):
        2024-11-21 08:32:00,245,Before Meal,
        2024-11-21 09:15:00,138,After Meal,some comment
        2024-11-21 10:00:00,7.6,No Meal,          ← mmol/L when meter set to mmol/L

    Returns dicts with synthetic column names so the existing import UI works:
        {"Timestamp": ..., "Glucose Value": ..., "Meal": ..., "Comment": ...}
    """
    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",", 3)]
        if len(parts) < 2:
            continue
        row: dict = {
            "Timestamp": parts[0],
            "Glucose Value": parts[1] if len(parts) > 1 else "",
            "Meal": parts[2] if len(parts) > 2 else "",
            "Comment": parts[3] if len(parts) > 3 else "",
        }
        rows.append(row)
    return rows


def _parse_contour_app_csv(text: str) -> list[dict]:
    """
    Parse Contour Diabetes App export (ContourCSVReport_*.csv).

    Header (EN):  #,Date and Time,Readings [mg/dL],Meal Marker,Data Source,Notes,...
    Header (DE):  #,Datum und Zeit,Messungen [mg/dL],Mahlzeit-Markierung,...

    The file is BOM-stripped already (utf-8-sig decode in caller).
    Date formats: MM/DD/YY HH:MM (EN) or DD.MM.YY HH:MM (DE).

    We normalise to our canonical column names so suggest_import_columns picks them up.
    """
    stream = io.StringIO(text)
    reader = csv.DictReader(stream)
    if reader.fieldnames is None:
        return []

    # Map actual header names to canonical names
    field_map: dict[str, str] = {}
    for f in reader.fieldnames:
        fl = f.lower().strip()
        if "date and time" in fl or "datum und zeit" in fl:
            field_map[f] = "Timestamp"
        elif "readings" in fl or "messungen" in fl:
            field_map[f] = "Glucose Value"
        elif "meal marker" in fl or "mahlzeit" in fl:
            field_map[f] = "Meal"
        elif "notes" in fl or "notizen" in fl:
            field_map[f] = "Comment"

    rows = []
    for raw_row in reader:
        if not any(str(v).strip() for v in raw_row.values() if v is not None):
            continue
        row = {field_map.get(k, k): v for k, v in raw_row.items()}
        # Skip rows with no glucose reading (e.g. meal-only log entries)
        glucose = row.get("Glucose Value", "")
        if not str(glucose).strip():
            continue
        rows.append(row)
    return rows


def parse_xlsx(content: bytes) -> list[dict]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.rows)
    if not rows:
        return []
    headers = [str(cell.value).strip() if cell.value is not None else "" for cell in rows[0]]
    result: list[dict] = []
    for row in rows[1:]:
        values = [cell.value for cell in row]
        row_obj = {headers[i]: values[i] if i < len(values) else None for i in range(len(headers))}
        result.append(row_obj)
    return result


def parse_txt(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig", errors="ignore")
    result = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "," in line:
            parts = [p.strip() for p in line.split(",", 1)]
        else:
            parts = line.split(maxsplit=1)
        if len(parts) != 2:
            result.append({"raw": line})
            continue
        result.append({"datetime": parts[0], "glucose": parts[1]})
    return result


# ---------------------------------------------------------------------------
# Format detection (by file extension)
# ---------------------------------------------------------------------------

def detect_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".xlsx":
        return "xlsx"
    if suffix == ".txt":
        return "txt"
    raise ValueError("Unsupported file format")


# ---------------------------------------------------------------------------
# Value parsing / normalisation
# ---------------------------------------------------------------------------

def normalize_datetime(value: str) -> datetime:
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid datetime '{value}'")


def parse_glucose_value(raw: object, glucose_column: str) -> float:
    text = str(raw).strip().replace(",", "")
    if not text:
        raise ValueError("Glucose value is empty")
    value = float(text)
    if "mmol" in glucose_column.lower():
        # Explicit mmol/L column name
        value = value * MMOL_L_TO_MG_DL
    elif value < 35:
        # Heuristic: no meter reads below 35 mg/dL in practice; likely mmol/L
        # glucometerutils uses "Glucose Value" column with no unit in name when
        # the meter is set to mmol/L — we detect by magnitude.
        value = value * MMOL_L_TO_MG_DL
    return value


def resolve_glucose_reading(row: dict, glucose_column: str) -> tuple[object, str]:
    primary = row.get(glucose_column)
    if str(primary or "").strip():
        return primary, glucose_column

    for column in _LIBRE_GLUCOSE_FALLBACK_COLUMNS:
        if column == glucose_column:
            continue
        candidate = row.get(column)
        if str(candidate or "").strip():
            return candidate, column

    raise ValueError("Glucose value is empty")


# ---------------------------------------------------------------------------
# Column suggestion (for the import UI)
# ---------------------------------------------------------------------------

def suggest_import_columns(columns: list[str]) -> dict[str, str | None]:
    datetime_col = None
    glucose_col = None
    for col in columns:
        lower = col.lower()

        # glucometerutils dump synthetic names
        if datetime_col is None and lower == "timestamp":
            datetime_col = col
        if glucose_col is None and lower == "glucose value":
            glucose_col = col

        # Contour app
        if datetime_col is None and "date and time" in lower:
            datetime_col = col
        if glucose_col is None and "readings" in lower:
            glucose_col = col

        # FreeStyle Libre
        if datetime_col is None and ("device timestamp" in lower or "date/time" in lower):
            datetime_col = col
        if glucose_col is None and "glucose" in lower and "mmol" in lower:
            glucose_col = col
        elif glucose_col is None and "historic glucose" in lower:
            glucose_col = col
        elif glucose_col is None and lower in ("glucose", "glucose_value", "value"):
            glucose_col = col

    return {"datetime_column": datetime_col, "glucose_column": glucose_col}


def row_to_string(row: dict) -> str:
    return json.dumps(row, default=str)
