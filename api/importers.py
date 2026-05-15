import csv
import io
import json
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook


def _non_empty_row(row: dict) -> bool:
    return any(str(v).strip() for v in row.values() if v is not None)


def parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig", errors="ignore")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    # Some glucose exports include title rows before the real header.
    header_idx = 0
    for i, line in enumerate(lines[:20]):
        lower = line.lower()
        if any(token in lower for token in ("date", "time", "glucose", "value", "reading")):
            header_idx = i
            break

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
    except ValueError as exc:
        raise ValueError(f"Invalid datetime '{value}'") from exc


def row_to_string(row: dict) -> str:
    return json.dumps(row, default=str)
