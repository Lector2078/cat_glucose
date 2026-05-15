import csv
import io
import json
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

MMOL_L_TO_MG_DL = 18.0182
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
)


def _non_empty_row(row: dict) -> bool:
    return any(str(v).strip() for v in row.values() if v is not None)


def _find_csv_header_idx(lines: list[str]) -> int:
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


def parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig", errors="ignore")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []

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

    # Fallback when sniffer picks the wrong delimiter.
    for delimiter in (";", ",", "\t", "|"):
        stream = io.StringIO(body)
        reader = csv.DictReader(stream, delimiter=delimiter)
        rows = [dict(row) for row in reader if _non_empty_row(row)]
        if len(rows) > 0 and len(rows[0].keys()) > 1:
            return rows
    return []


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
        # Accept either "timestamp,value" or "timestamp value"
        if "," in line:
            parts = [p.strip() for p in line.split(",", 1)]
        else:
            parts = line.split(maxsplit=1)
        if len(parts) != 2:
            result.append({"raw": line})
            continue
        result.append({"datetime": parts[0], "glucose": parts[1]})
    return result


def detect_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".xlsx":
        return "xlsx"
    if suffix == ".txt":
        return "txt"
    raise ValueError("Unsupported file format")


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


def suggest_import_columns(columns: list[str]) -> dict[str, str | None]:
    datetime_col = None
    glucose_col = None
    for col in columns:
        lower = col.lower()
        if datetime_col is None and ("device timestamp" in lower or lower == "timestamp" or "date/time" in lower):
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
