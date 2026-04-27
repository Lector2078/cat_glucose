from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class CatBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    birth_date: str | None = None
    notes: str | None = None


class CatCreate(CatBase):
    pass


class CatRead(CatBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ReadingBase(BaseModel):
    cat_id: int
    reading_at: datetime
    glucose_value: float = Field(ge=10, le=1000)
    unit: str = "mg/dL"
    context: str | None = None
    notes: str | None = None


class ReadingCreate(ReadingBase):
    source: Literal["manual", "import"] = "manual"


class ReadingRead(ReadingBase):
    id: int
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportJobRead(BaseModel):
    id: int
    filename: str
    format: str
    status: str
    rows_total: int
    rows_inserted: int
    rows_rejected: int
    error_report_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
